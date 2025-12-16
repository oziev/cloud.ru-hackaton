
import redis
from typing import Optional
from shared.config.settings import settings
class RedisClient:
    def __init__(self):
        self._clients = {}
        self.redis_host = settings.redis_host
        self.redis_port = settings.redis_port
        self.redis_db_pubsub = settings.redis_db_pubsub
    def get_client(self, db: int = 0, decode_responses: bool = True) -> redis.Redis:
        key = f"{db}_{decode_responses}"
        if key not in self._clients:
            import os
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                from urllib.parse import urlparse
                parsed = urlparse(redis_url)
                base_url = f"redis://{parsed.netloc}"
                self._clients[key] = redis.from_url(
                    base_url,
                    db=db,
                    decode_responses=decode_responses,
                    socket_connect_timeout=5
                )
            else:
                self._clients[key] = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=db,
                    decode_responses=decode_responses,
                    socket_connect_timeout=5
                )
        return self._clients[key]
    @property
    def queue(self) -> redis.Redis:
        return self.get_client(settings.redis_db_queue)
    @property
    def result(self) -> redis.Redis:
        return self.get_client(settings.redis_db_result)
    @property
    def cache(self) -> redis.Redis:
        return self.get_client(settings.redis_db_cache)
    @property
    def pubsub(self) -> redis.Redis:
        return self.get_client(settings.redis_db_pubsub)
    def publish_event(self, channel: str, event: dict):
        import json
        self.pubsub.publish(channel, json.dumps(event))
    def subscribe_channel(self, channel: str):
        pubsub_obj = self.pubsub.pubsub(ignore_subscribe_messages=True)
        pubsub_obj.subscribe(channel)
        return pubsub_obj
    async def subscribe_channel_async(self, channel: str):
        import redis.asyncio as aioredis
        import os
        # Используем REDIS_URL из окружения, если доступен, иначе используем настройки
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            from urllib.parse import urlparse
            parsed = urlparse(redis_url)
            base_url = f"redis://{parsed.netloc}"
            redis_async = aioredis.from_url(
                base_url,
                db=self.redis_db_pubsub,
                decode_responses=True
            )
        else:
            redis_async = aioredis.from_url(
                f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db_pubsub}",
                decode_responses=True
            )
        pubsub_obj = redis_async.pubsub()
        await pubsub_obj.subscribe(channel)
        return pubsub_obj, redis_async
    def create_vector_index(self, index_name: str, vector_dim: int = 768):
        try:
            # Redis Search может создавать индексы только на базе данных 0
            # Используем базу 0 для индексов, но с префиксом для изоляции
            client = self.get_client(0, decode_responses=False)
            try:
                client.execute_command("FT.INFO", index_name)
                return True
            except (redis.ResponseError, redis.exceptions.ResponseError):
                pass
            client.execute_command(
                "FT.CREATE", index_name,
                "ON", "HASH",
                "PREFIX", "1", f"test:{index_name}:",
                "SCHEMA",
                "test_id", "TEXT",
                "test_name", "TEXT",
                "embedding", "VECTOR", "FLAT", "6", "DIM", str(vector_dim), "DISTANCE_METRIC", "COSINE"
            )
            return True
        except Exception as e:
            from shared.utils.logger import api_logger
            api_logger.warning(f"Error creating vector index (will continue without vector search): {e}")
            # Не критично - продолжаем без векторного поиска
            return False
    def save_vector(self, index_name: str, test_id: str, test_name: str, embedding: list):
        try:
            # Используем базу 0 для совместимости с Redis Search индексами
            client = self.get_client(0, decode_responses=False)
            key = f"test:{index_name}:{test_id}"
            import struct
            embedding_bytes = struct.pack(f"{len(embedding)}f", *embedding)
            client.hset(
                key,
                mapping={
                    "test_id": test_id.encode() if isinstance(test_id, str) else test_id,
                    "test_name": test_name.encode() if isinstance(test_name, str) else test_name,
                    "embedding": embedding_bytes
                }
            )
            return True
        except Exception as e:
            from shared.utils.logger import api_logger
            api_logger.warning(f"Error saving vector (will continue without vector search): {e}")
            # Не критично - продолжаем без векторного поиска
            return False
    def search_similar_vectors(self, index_name: str, query_vector: list, top_k: int = 10, threshold: float = 0.85):
        try:
            # Используем базу 0 для совместимости с Redis Search индексами
            client = self.get_client(0, decode_responses=False)
            import struct
            query_bytes = struct.pack(f"{len(query_vector)}f", *query_vector)
            results = client.execute_command(
                "FT.SEARCH", index_name,
                f"*=>[KNN $top_k @embedding $query_vector AS distance]",
                "PARAMS", "2", "query_vector", query_bytes, "top_k", str(top_k),
                "SORTBY", "distance", "ASC",
                "RETURN", "2", "test_id", "distance",
                "LIMIT", "0", str(top_k)
            )
            similar_tests = []
            if results and len(results) > 1:
                count = results[0]
                i = 1
                while i < len(results):
                    if i + 1 < len(results):
                        key = results[i]
                        fields = results[i + 1]
                        test_id_bytes = fields.get(b"test_id", b"")
                        test_id = test_id_bytes.decode() if isinstance(test_id_bytes, bytes) else str(test_id_bytes)
                        distance_bytes = fields.get(b"distance", b"0")
                        if isinstance(distance_bytes, bytes):
                            try:
                                distance = float(distance_bytes.decode())
                            except:
                                distance = 1.0
                        else:
                            distance = float(distance_bytes)
                        similarity = max(0.0, 1.0 - distance)
                        if similarity >= threshold:
                            similar_tests.append({
                                "test_id": test_id,
                                "similarity": similarity
                            })
                    i += 2
            return similar_tests
        except Exception as e:
            from shared.utils.logger import api_logger
            api_logger.error(f"Error searching similar vectors: {e}", exc_info=True)
            return []
redis_client = RedisClient()