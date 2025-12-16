
import httpx
import base64
from typing import Dict, Any, List, Optional
from shared.utils.logger import agent_logger
class JiraClient:
    def __init__(self, jira_url: str, jira_token: str = None, jira_email: str = None):
        self.jira_url = jira_url
        self.jira_token = jira_token
        self.jira_email = jira_email
    def _get_headers(self) -> Dict[str, str]:
        if self.jira_email and self.jira_token:
            credentials = base64.b64encode(
                f"{self.jira_email}:{self.jira_token}".encode()
            ).decode()
            return {
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json"
            }
        else:
            return {
                "Authorization": f"Bearer {self.jira_token}",
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
        if not self.jira_url:
            agent_logger.warning("Jira URL not configured")
            return []
        if not self.jira_token and not self.jira_email:
            agent_logger.warning("Jira credentials not configured")
            return []
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = self._get_headers()
            jql_parts = []
            if project_key:
                jql_parts.append(f"project = {project_key}")
            if status:
                jql_parts.append(f"status IN ({', '.join(status)})")
            if priority:
                jql_parts.append(f"priority IN ({', '.join(priority)})")
            if date_from:
                jql_parts.append(f"created >= {date_from}")
            if date_to:
                jql_parts.append(f"created <= {date_to}")
            jql = " AND ".join(jql_parts) if jql_parts else "ORDER BY created DESC"
            try:
                url = f"{self.jira_url}/rest/api/3/search"
                payload = {
                    "jql": jql,
                    "maxResults": 100,
                    "fields": ["summary", "description", "status", "priority", "created", "updated", "assignee", "reporter", "components"]
                }
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                issues = data.get("issues", [])
                normalized = []
                for issue in issues:
                    fields = issue.get("fields", {})
                    normalized.append({
                        "id": issue.get("id"),
                        "key": issue.get("key"),
                        "summary": fields.get("summary"),
                        "description": fields.get("description"),
                        "status": fields.get("status", {}).get("name"),
                        "priority": fields.get("priority", {}).get("name"),
                        "severity": None,
                        "created_at": fields.get("created"),
                        "updated_at": fields.get("updated"),
                        "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
                        "reporter": fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
                        "affected_components": [c.get("name") for c in fields.get("components", [])],
                        "source": "jira"
                    })
                return normalized
            except httpx.HTTPStatusError as e:
                agent_logger.error(f"Jira API error: {e.response.status_code} - {e.response.text}")
                return []
            except Exception as e:
                agent_logger.error(f"Error fetching Jira defects: {e}", exc_info=True)
                return []
    async def test_connection(self) -> Dict[str, Any]:
        if not self.jira_url:
            return {"connected": False, "error": "Jira URL не настроен"}
        if not self.jira_token and not self.jira_email:
            return {"connected": False, "error": "Jira token или email не настроен"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = self._get_headers()
                url = f"{self.jira_url}/rest/api/3/myself"
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return {"connected": True, "error": None}
        except Exception as e:
            return {"connected": False, "error": str(e)}