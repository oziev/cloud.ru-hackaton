
import httpx
from typing import Dict, Any, List, Optional
from shared.utils.logger import agent_logger
class AllureClient:
    def __init__(self, allure_testops_url: str, allure_testops_token: str):
        self.allure_testops_url = allure_testops_url
        self.allure_testops_token = allure_testops_token
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.allure_testops_token}",
            "Content-Type": "application/json"
        }
    async def fetch_defects(
        self,
        project_key: str = None,
        status: List[str] = None,
        priority: List[str] = None,
        date_from: str = None,
        date_to: str = None
    ) -> List[Dict[str, Any]]:
        if not self.allure_testops_url or not self.allure_testops_token:
            agent_logger.warning("Allure TestOps credentials not configured")
            return []
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = self._get_headers()
            params = {}
            if project_key:
                params["project"] = project_key
            if status:
                params["status"] = ",".join(status)
            if priority:
                params["priority"] = ",".join(priority)
            if date_from:
                params["dateFrom"] = date_from
            if date_to:
                params["dateTo"] = date_to
            try:
                url = f"{self.allure_testops_url}/api/rs/defect"
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                defects = data.get("content", [])
                normalized = []
                for defect in defects:
                    normalized.append({
                        "id": defect.get("id"),
                        "key": defect.get("key"),
                        "summary": defect.get("name"),
                        "description": defect.get("description"),
                        "status": defect.get("status", {}).get("name"),
                        "priority": defect.get("priority", {}).get("name"),
                        "severity": defect.get("severity"),
                        "created_at": defect.get("createdDate"),
                        "updated_at": defect.get("updatedDate"),
                        "assignee": defect.get("assignee", {}).get("login"),
                        "reporter": defect.get("reporter", {}).get("login"),
                        "affected_components": defect.get("affectedComponents", []),
                        "source": "allure"
                    })
                return normalized
            except httpx.HTTPStatusError as e:
                agent_logger.error(f"Allure API error: {e.response.status_code} - {e.response.text}")
                return []
            except Exception as e:
                agent_logger.error(f"Error fetching Allure defects: {e}", exc_info=True)
                return []
    async def test_connection(self) -> Dict[str, Any]:
        if not self.allure_testops_url or not self.allure_testops_token:
            return {"connected": False, "error": "Allure TestOps credentials не настроены"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = self._get_headers()
                url = f"{self.allure_testops_url}/api/rs/user"
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return {"connected": True, "error": None}
        except Exception as e:
            return {"connected": False, "error": str(e)}