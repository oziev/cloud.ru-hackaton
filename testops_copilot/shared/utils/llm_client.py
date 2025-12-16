
import asyncio
from typing import Dict, Any, Optional
from shared.config.settings import settings
from shared.utils.redis_client import redis_client
from shared.utils.logger import llm_logger
import hashlib
import json
try:
    from openai import OpenAI, AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    import httpx
class LLMClient:
    def __init__(self):
        self.base_url = settings.cloud_ru_foundation_models_url
        self.api_key = settings.cloud_ru_api_key or getattr(settings, 'evolution_llm_api_key', None)
        self.default_model = getattr(settings, 'cloud_ru_default_model', 'ai-sage/GigaChat3-10B-A1.8B')
        if OPENAI_AVAILABLE:
            try:
                self._openai_client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
                llm_logger.info("OpenAI client initialized with API-KEY")
            except Exception as e:
                llm_logger.warning(f"Failed to initialize OpenAI client: {e}, falling back to httpx")
                self._openai_client = None
        else:
            self._openai_client = None
            llm_logger.warning("OpenAI library not available, using httpx fallback")
        if not self._openai_client:
            import httpx
            self._http_client: Optional[httpx.AsyncClient] = None
    async def _get_http_client(self):
        if not OPENAI_AVAILABLE:
            import httpx
            if self._http_client is None:
                self._http_client = httpx.AsyncClient(timeout=60.0)
            return self._http_client
        return None
    async def close(self):
        if self._openai_client:
            await self._openai_client.close()
        if hasattr(self, '_http_client') and self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        use_cache: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        if model is None:
            model = self.default_model
        if use_cache:
            cache_key = f"llm_cache:{hashlib.sha256((system_prompt + prompt + model).encode()).hexdigest()}"
            cached = redis_client.cache.get(cache_key)
            if cached:
                return json.loads(cached)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        max_retries = 3
        base_delay = 1.0
        for attempt in range(max_retries):
            try:
                if self._openai_client:
                    try:
                        response = await self._openai_client.chat.completions.create(
                            model=model,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            **kwargs
                        )
                        result = {
                            "choices": [{
                                "message": {
                                    "role": response.choices[0].message.role,
                                    "content": response.choices[0].message.content
                                }
                            }],
                            "usage": {
                                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                                "total_tokens": response.usage.total_tokens if response.usage else 0
                            }
                        }
                        if use_cache:
                            try:
                                redis_client.cache.setex(
                                    cache_key,
                                    3600,
                                    json.dumps(result)
                                )
                            except Exception as cache_error:
                                llm_logger.warning(f"Failed to cache LLM response: {cache_error}")
                        llm_logger.info(
                            "LLM generation successful",
                            extra={
                                "model": model,
                                "tokens_used": result.get("usage", {}).get("total_tokens", 0)
                            }
                        )
                        return result
                    except Exception as e:
                        llm_logger.warning(f"OpenAI client error: {e}, falling back to httpx")
                        if attempt == max_retries - 1:
                            raise
                        await asyncio.sleep(base_delay * (2 ** attempt))
                        continue
                if not OPENAI_AVAILABLE:
                    import httpx
                    client = await self._get_http_client()
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": messages,
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                            **kwargs,
                        },
                    )
                    if response.status_code != 200:
                        error_text = response.text[:1000]
                        error_json = None
                        try:
                            error_json = response.json()
                        except:
                            pass
                        llm_logger.error(
                            f"LLM API Error {response.status_code}",
                            extra={
                                "url": f"{self.base_url}/chat/completions",
                                "status_code": response.status_code,
                                "response_text": error_text,
                                "error_json": error_json
                            }
                        )
                    if response.status_code == 429:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            await asyncio.sleep(delay)
                            continue
                    response.raise_for_status()
                    result = response.json()
                    if use_cache:
                        try:
                            redis_client.cache.setex(
                                cache_key,
                                3600,
                                json.dumps(result)
                            )
                        except Exception as cache_error:
                            llm_logger.warning(f"Failed to cache LLM response: {cache_error}")
                    llm_logger.info(
                        "LLM generation successful",
                        extra={
                            "model": model,
                            "tokens_used": result.get("usage", {}).get("total_tokens", 0)
                        }
                    )
                    return result
            except Exception as e:
                if attempt == max_retries - 1:
                    llm_logger.error(f"LLM generation failed after {max_retries} attempts: {e}", exc_info=True)
                    raise
                await asyncio.sleep(base_delay * (2 ** attempt))
        raise Exception("Failed to generate after retries")
    async def generate_embeddings(self, text: str) -> list:
        try:
            cache_key = f"embedding:{hashlib.sha256(text.encode()).hexdigest()}"
            try:
                cached = redis_client.cache.get(cache_key)
                if cached:
                    import json
                    return json.loads(cached)
            except:
                pass
            if self._openai_client:
                try:
                    response = await self._openai_client.embeddings.create(
                        model="text-embedding-ada-002",
                        input=text
                    )
                    embedding = response.data[0].embedding
                    import math
                    norm = math.sqrt(sum(x*x for x in embedding))
                    if norm > 0:
                        embedding = [x / norm for x in embedding]
                    try:
                        import json
                        redis_client.cache.setex(cache_key, 86400, json.dumps(embedding))
                    except:
                        pass
                    return embedding
                except Exception as e:
                    llm_logger.warning(f"Failed to generate embeddings via OpenAI SDK: {e}, falling back to hash-based")
            llm_logger.warning("Using hash-based embeddings fallback")
            hash_obj = hashlib.sha256(text.encode('utf-8'))
            hash_bytes = hash_obj.digest()
            embedding = []
            for i in range(768):
                byte_idx = i % len(hash_bytes)
                next_byte_idx = (i + 1) % len(hash_bytes)
                value = (hash_bytes[byte_idx] + hash_bytes[next_byte_idx] * 256) / 65535.0
                embedding.append(float(value))
            import math
            norm = math.sqrt(sum(x*x for x in embedding))
            if norm > 0:
                embedding = [x / norm for x in embedding]
            return embedding
        except Exception as e:
            llm_logger.error(f"Error generating embeddings: {e}", exc_info=True)
            hash_obj = hashlib.sha256(text.encode('utf-8'))
            return [float(b) / 255.0 for b in hash_obj.digest()[:384]]
llm_client = LLMClient()