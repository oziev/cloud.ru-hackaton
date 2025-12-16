
import hashlib
import asyncio
import numpy as np
from typing import Dict, List, Any
from shared.utils.database import get_db
from shared.models.database import TestCase
from shared.utils.llm_client import llm_client
from shared.utils.redis_client import redis_client
from shared.utils.logger import agent_logger
class OptimizerAgent:
    async def optimize(
        self,
        tests: List[Dict[str, str]],
        requirements: List[str],
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        options = options or {}
        similarity_threshold = options.get("similarity_threshold", 0.85)
        include_existing = options.get("include_existing", False)
        exact_duplicates = self._find_exact_duplicates(tests)
        semantic_duplicates = await self._find_semantic_duplicates(tests, similarity_threshold)
        llm_duplicates = await self._llm_analysis_duplicates(semantic_duplicates, tests, similarity_threshold)
        coverage_result = self._analyze_coverage(tests, requirements)
        all_duplicates = exact_duplicates + semantic_duplicates + llm_duplicates
        unique_tests = self._remove_duplicates(tests, all_duplicates)
        return {
            "optimized_tests": unique_tests,
            "duplicates_found": len(all_duplicates),
            "duplicates": all_duplicates,
            "coverage_score": coverage_result["score"],
            "coverage_details": coverage_result["details"],
            "gaps": coverage_result["gaps"],
            "recommendations": self._generate_recommendations(all_duplicates, coverage_result)
        }
    def _find_exact_duplicates(self, tests: List[Dict]) -> List[Dict]:
        duplicates = []
        seen_hashes = {}
        for test in tests:
            code_hash = hashlib.sha256(test["test_code"].encode()).hexdigest()
            if code_hash in seen_hashes:
                duplicates.append({
                    "test_ids": [seen_hashes[code_hash], test["test_id"]],
                    "type": "exact",
                    "similarity_score": 1.0
                })
            else:
                seen_hashes[code_hash] = test["test_id"]
        return duplicates
    async def _find_semantic_duplicates(self, tests: List[Dict], threshold: float) -> List[Dict]:
        if len(tests) < 2:
            return []
        try:
            index_name = "idx:test_embeddings"
            use_redisearch = redis_client.create_vector_index(index_name, vector_dim=768)
            agent_logger.info(f"Generating embeddings for {len(tests)} tests")
            embeddings = []
            test_texts = []
            # Добавляем таймаут для каждого эмбеддинга (10 секунд)
            import asyncio
            for i, test in enumerate(tests):
                test_text = f"{test.get('test_name', '')} {test.get('test_code', '')}"
                test_texts.append(test_text)
                try:
                    # Генерируем эмбеддинг с таймаутом
                    embedding = await asyncio.wait_for(
                        llm_client.generate_embeddings(test_text),
                        timeout=10.0
                    )
                    embeddings.append(embedding)
                    if (i + 1) % 5 == 0:
                        agent_logger.info(f"Generated embeddings for {i + 1}/{len(tests)} tests")
                except asyncio.TimeoutError:
                    agent_logger.warning(f"Embedding generation timeout for test {i + 1}, using hash-based fallback")
                    # Используем хеш-основанный эмбеддинг как fallback
                    import hashlib
                    import numpy as np
                    hash_val = int(hashlib.sha256(test_text.encode()).hexdigest()[:8], 16)
                    # Создаем простой вектор на основе хеша
                    embedding = [float((hash_val >> j) & 1) for j in range(768)]
                    embeddings.append(embedding)
                except Exception as e:
                    agent_logger.error(f"Error generating embedding for test {i + 1}: {e}")
                    # Используем хеш-основанный эмбеддинг как fallback
                    import hashlib
                    hash_val = int(hashlib.sha256(test_text.encode()).hexdigest()[:8], 16)
                    embedding = [float((hash_val >> j) & 1) for j in range(768)]
                embeddings.append(embedding)
                if use_redisearch:
                    redis_client.save_vector(
                        index_name,
                        test["test_id"],
                        test.get("test_name", ""),
                        embedding
                    )
            duplicates = []
            if use_redisearch:
                agent_logger.info("Using RediSearch for vector search")
                for i, test in enumerate(tests):
                    similar = redis_client.search_similar_vectors(
                        index_name,
                        embeddings[i],
                        top_k=10,
                        threshold=threshold
                    )
                    for similar_test in similar:
                        if similar_test["test_id"] != test["test_id"]:
                            pair_exists = any(
                                (dup["test_ids"][0] == test["test_id"] and dup["test_ids"][1] == similar_test["test_id"]) or
                                (dup["test_ids"][1] == test["test_id"] and dup["test_ids"][0] == similar_test["test_id"])
                                for dup in duplicates
                            )
                            if not pair_exists:
                                duplicates.append({
                                    "test_ids": [test["test_id"], similar_test["test_id"]],
                                    "type": "semantic_redisearch",
                                    "similarity_score": similar_test["similarity"],
                                    "test_names": [
                                        test.get("test_name", ""),
                                        similar_test.get("test_name", "")
                                    ]
                                })
            else:
                agent_logger.info("Using numpy cosine similarity (RediSearch not available)")
                embeddings_array = np.array(embeddings)
                for i in range(len(tests)):
                    for j in range(i + 1, len(tests)):
                        similarity = self._cosine_similarity(
                            embeddings_array[i],
                            embeddings_array[j]
                        )
                        if similarity >= threshold:
                            duplicates.append({
                                "test_ids": [tests[i]["test_id"], tests[j]["test_id"]],
                                "type": "semantic",
                                "similarity_score": float(similarity),
                                "test_names": [
                                    tests[i].get("test_name", ""),
                                    tests[j].get("test_name", "")
                                ]
                            })
            agent_logger.info(f"Found {len(duplicates)} semantic duplicates")
            return duplicates
        except Exception as e:
            agent_logger.error(f"Error finding semantic duplicates: {e}", exc_info=True)
            return []
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        try:
            vec1 = np.array(vec1)
            vec2 = np.array(vec2)
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
        except Exception as e:
            agent_logger.warning(f"Error calculating cosine similarity: {e}")
            return 0.0
    def _analyze_coverage(self, tests: List[Dict], requirements: List[str]) -> Dict:
        coverage_details = {}
        gaps = []
        for idx, requirement in enumerate(requirements):
            covering_tests = []
            for test in tests:
                if requirement.lower() in test["test_code"].lower():
                    covering_tests.append(test["test_id"])
            is_covered = len(covering_tests) > 0
            coverage_details[f"requirement_{idx}"] = {
                "text": requirement,
                "covered": is_covered,
                "tests": covering_tests,
                "quality": "good" if len(covering_tests) >= 2 else "insufficient"
            }
            if not is_covered:
                gaps.append({
                    "requirement": f"requirement_{idx}",
                    "description": f"Отсутствуют тесты для: {requirement}"
                })
        covered_count = sum(1 for detail in coverage_details.values() if detail["covered"])
        coverage_score = covered_count / len(requirements) if requirements else 0.0
        return {
            "score": coverage_score,
            "details": coverage_details,
            "gaps": gaps
        }
    def _remove_duplicates(self, tests: List[Dict], duplicates: List[Dict]) -> List[Dict]:
        duplicate_ids = set()
        for dup in duplicates:
            duplicate_ids.update(dup["test_ids"][1:])
        return [test for test in tests if test["test_id"] not in duplicate_ids]
    async def _llm_analysis_duplicates(self, semantic_duplicates: List[Dict], tests: List[Dict], threshold: float) -> List[Dict]:
        llm_duplicates = []
        ambiguous_cases = []
        for dup in semantic_duplicates:
            similarity = dup.get("similarity_score", 0.0)
            if 0.75 < similarity < 0.85:
                ambiguous_cases.append(dup)
        if not ambiguous_cases:
            return []
        agent_logger.info(f"Analyzing {len(ambiguous_cases)} ambiguous cases with LLM")
        from shared.utils.redis_client import redis_client
        import json
        for case in ambiguous_cases:
            test_id_1, test_id_2 = case["test_ids"]
            cache_key = f"llm_analysis:{test_id_1}:{test_id_2}"
            cached_result = redis_client.cache.get(cache_key)
            if cached_result:
                try:
                    result = json.loads(cached_result)
                    if result.get("is_duplicate", False):
                        llm_duplicates.append({
                            "test_ids": case["test_ids"],
                            "type": "semantic_llm",
                            "similarity_score": case["similarity_score"],
                            "test_names": case.get("test_names", [])
                        })
                    continue
                except:
                    pass
            test1 = next((t for t in tests if t["test_id"] == test_id_1), None)
            test2 = next((t for t in tests if t["test_id"] == test_id_2), None)
            if not test1 or not test2:
                continue
            try:
                prompt = f
                response = await llm_client.generate(
                    prompt=prompt,
                    max_tokens=10,
                    temperature=0.1
                )
                content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
                is_duplicate = "YES" in content.upper()
                result = {"is_duplicate": is_duplicate, "similarity": case["similarity_score"]}
                redis_client.cache.setex(cache_key, 86400, json.dumps(result))
                if is_duplicate:
                    llm_duplicates.append({
                        "test_ids": case["test_ids"],
                        "type": "semantic_llm",
                        "similarity_score": case["similarity_score"],
                        "test_names": case.get("test_names", [])
                    })
            except Exception as e:
                agent_logger.warning(f"Error in LLM analysis: {e}")
        agent_logger.info(f"LLM analysis found {len(llm_duplicates)} additional duplicates")
        return llm_duplicates
    def _generate_recommendations(self, duplicates: List[Dict], coverage: Dict) -> List[str]:
        recommendations = []
        if duplicates:
            recommendations.append(f"Удалить {len(duplicates)} дубликатов")
        if coverage["gaps"]:
            recommendations.append(f"Добавить тесты для {len(coverage['gaps'])} непокрытых требований")
        return recommendations