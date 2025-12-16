
import yaml
import json
from typing import Dict, Any, List, Optional
import httpx
class OpenAPIParser:
    def __init__(self):
        pass
    async def parse_from_url(self, url: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                except httpx.ConnectError as e:
                    error_msg = str(e)
                    if "Name or service not known" in error_msg or "[Errno -2]" in error_msg:
                        raise ValueError(
                            f"Не удалось подключиться к {url}. "
                            f"Проверьте правильность URL и доступность сервера. "
                            f"Возможно, домен не существует или недоступен."
                        )
                    elif "Connection refused" in error_msg:
                        raise ValueError(
                            f"Соединение отклонено для {url}. "
                            f"Сервер недоступен или не отвечает."
                        )
                    else:
                        raise ValueError(f"Ошибка подключения к {url}: {error_msg}")
                except httpx.TimeoutException:
                    raise ValueError(
                        f"Превышено время ожидания при получении {url}. "
                        f"Сервер не отвечает в течение 30 секунд."
                    )
                except httpx.HTTPStatusError as e:
                    raise ValueError(
                        f"HTTP ошибка при получении OpenAPI спецификации из {url}: "
                        f"статус {e.response.status_code}. "
                        f"Проверьте доступность URL и права доступа."
                    )
                
                content = response.text
                if not content or not content.strip():
                    raise ValueError(f"Получен пустой ответ от {url}")
                
                if url.endswith('.yaml') or url.endswith('.yml') or content.strip().startswith('---'):
                    try:
                        return yaml.safe_load(content)
                    except yaml.YAMLError as e:
                        raise ValueError(f"Ошибка парсинга YAML из {url}: {e}")
                else:
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Ошибка парсинга JSON из {url}: {e}")
        except ValueError:
            # Пробрасываем ValueError как есть
            raise
        except Exception as e:
            error_msg = str(e)
            if "Name or service not known" in error_msg or "[Errno -2]" in error_msg:
                raise ValueError(
                    f"Не удалось подключиться к {url}. "
                    f"Проверьте правильность URL и доступность сервера."
                )
            else:
                raise ValueError(f"Ошибка при получении OpenAPI спецификации из {url}: {error_msg}")
    def parse_from_content(self, content: str, format: str = "yaml") -> Dict[str, Any]:
        if format.lower() == "yaml" or format.lower() == "yml":
            return yaml.safe_load(content)
        else:
            return json.loads(content)
    def extract_endpoints(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        endpoints = []
        paths = spec.get("paths", {})
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.lower() in ["get", "post", "put", "delete", "patch"]:
                    endpoint_info = {
                        "path": path,
                        "method": method.upper(),
                        "operation_id": operation.get("operationId", f"{method}_{path.replace('/', '_')}"),
                        "summary": operation.get("summary", ""),
                        "description": operation.get("description", ""),
                        "parameters": operation.get("parameters", []),
                        "request_body": operation.get("requestBody", {}),
                        "responses": operation.get("responses", {}),
                        "tags": operation.get("tags", []),
                        "security": operation.get("security", [])
                    }
                    endpoints.append(endpoint_info)
        return endpoints
    def extract_schemas(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        components = spec.get("components", {})
        schemas = components.get("schemas", {})
        return schemas
    def extract_examples(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        examples = {}
        paths = spec.get("paths", {})
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.lower() in ["get", "post", "put", "delete", "patch"]:
                    operation_id = operation.get("operationId", f"{method}_{path.replace('/', '_')}")
                    request_body = operation.get("requestBody", {})
                    if request_body:
                        content = request_body.get("content", {})
                        for content_type, content_schema in content.items():
                            if "example" in content_schema:
                                examples[f"{operation_id}_request"] = content_schema["example"]
                    responses = operation.get("responses", {})
                    for status_code, response_schema in responses.items():
                        content = response_schema.get("content", {})
                        for content_type, content_schema in content.items():
                            if "example" in content_schema:
                                examples[f"{operation_id}_response_{status_code}"] = content_schema["example"]
        return examples
    def get_endpoint_test_cases(self, endpoint: Dict[str, Any]) -> List[Dict[str, Any]]:
        test_cases = []
        test_cases.append({
            "type": "positive",
            "name": f"Test {endpoint['method']} {endpoint['path']} - Success",
            "description": f"Проверка успешного запроса {endpoint['method']} {endpoint['path']}",
            "expected_status": [200, 201, 204]
        })
        responses = endpoint.get("responses", {})
        if "400" in responses:
            test_cases.append({
                "type": "negative_validation",
                "name": f"Test {endpoint['method']} {endpoint['path']} - Validation Error",
                "description": f"Проверка ошибки валидации {endpoint['method']} {endpoint['path']}",
                "expected_status": [400]
            })
        if "401" in responses:
            test_cases.append({
                "type": "negative_auth",
                "name": f"Test {endpoint['method']} {endpoint['path']} - Unauthorized",
                "description": f"Проверка ошибки авторизации {endpoint['method']} {endpoint['path']}",
                "expected_status": [401]
            })
        if "403" in responses:
            test_cases.append({
                "type": "negative_forbidden",
                "name": f"Test {endpoint['method']} {endpoint['path']} - Forbidden",
                "description": f"Проверка ошибки доступа {endpoint['method']} {endpoint['path']}",
                "expected_status": [403]
            })
        if "404" in responses:
            test_cases.append({
                "type": "negative_not_found",
                "name": f"Test {endpoint['method']} {endpoint['path']} - Not Found",
                "description": f"Проверка ошибки не найден {endpoint['method']} {endpoint['path']}",
                "expected_status": [404]
            })
        if "422" in responses:
            test_cases.append({
                "type": "negative_validation",
                "name": f"Test {endpoint['method']} {endpoint['path']} - Validation Error",
                "description": f"Проверка ошибки валидации {endpoint['method']} {endpoint['path']}",
                "expected_status": [422]
            })
        return test_cases