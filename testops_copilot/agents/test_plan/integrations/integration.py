
from typing import Dict, Any, List, Optional
from shared.utils.logger import agent_logger
from shared.config.settings import settings
from .jira_client import JiraClient
from .allure_client import AllureClient
class DefectIntegration:
    def __init__(self):
        self.jira_url = getattr(settings, 'jira_url', None)
        self.jira_token = getattr(settings, 'jira_token', None)
        self.jira_email = getattr(settings, 'jira_email', None)
        self.allure_testops_url = getattr(settings, 'allure_testops_url', None)
        self.allure_testops_token = getattr(settings, 'allure_testops_token', None)
        if self.jira_url and not self.jira_url.startswith(('http://', 'https://')):
            agent_logger.warning(f"Jira URL должен начинаться с http:// или https://: {self.jira_url}")
            self.jira_url = None
        if self.allure_testops_url and not self.allure_testops_url.startswith(('http://', 'https://')):
            agent_logger.warning(f"Allure TestOps URL должен начинаться с http:// или https://: {self.allure_testops_url}")
            self.allure_testops_url = None
        self.jira_client = JiraClient(self.jira_url, self.jira_token, self.jira_email) if self.jira_url else None
        self.allure_client = AllureClient(self.allure_testops_url, self.allure_testops_token) if self.allure_testops_url and self.allure_testops_token else None
    async def fetch_defects(
        self,
        project_key: str = None,
        status: List[str] = None,
        priority: List[str] = None,
        date_from: str = None,
        date_to: str = None,
        source: str = "allure"
    ) -> List[Dict[str, Any]]:
        all_defects = []
        if source in ["allure", "all"] and self.allure_client:
            try:
                allure_defects = await self.allure_client.fetch_defects(
                    project_key=project_key,
                    status=status,
                    priority=priority,
                    date_from=date_from,
                    date_to=date_to
                )
                all_defects.extend(allure_defects)
            except Exception as e:
                agent_logger.error(f"Error fetching Allure defects: {e}", exc_info=True)
        if source in ["jira", "all"] and self.jira_client:
            try:
                jira_defects = await self.jira_client.fetch_defects(
                    project_key=project_key,
                    status=status,
                    priority=priority,
                    date_from=date_from,
                    date_to=date_to
                )
                all_defects.extend(jira_defects)
            except Exception as e:
                agent_logger.error(f"Error fetching Jira defects: {e}", exc_info=True)
        return all_defects
    async def test_connection(self, source: str = "all") -> Dict[str, Any]:
        results = {
            "jira": {"connected": False, "error": None},
            "allure": {"connected": False, "error": None}
        }
        if source in ["jira", "all"] and self.jira_client:
            results["jira"] = await self.jira_client.test_connection()
        if source in ["allure", "all"] and self.allure_client:
            results["allure"] = await self.allure_client.test_connection()
        return results
    def get_configuration_status(self) -> Dict[str, Any]:
        return {
            "jira": {
                "configured": bool(self.jira_url and self.jira_token),
                "url": self.jira_url if self.jira_url else None,
                "has_token": bool(self.jira_token),
                "has_email": bool(self.jira_email)
            },
            "allure": {
                "configured": bool(self.allure_testops_url and self.allure_testops_token),
                "url": self.allure_testops_url if self.allure_testops_url else None,
                "has_token": bool(self.allure_testops_token)
            }
        }