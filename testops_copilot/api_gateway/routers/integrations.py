
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
from agents.test_plan.defect_integration import DefectIntegration
from shared.utils.logger import api_logger
router = APIRouter(prefix="/integrations", tags=["Integrations"])
class TestConnectionResponse(BaseModel):
    jira: Dict[str, Any]
    allure: Dict[str, Any]
    configuration_status: Dict[str, Any]
@router.get("/test-connection", response_model=TestConnectionResponse)
async def test_connection(
    source: Optional[str] = "all"
):
    try:
        integration = DefectIntegration()
        connection_results = await integration.test_connection(source=source)
        config_status = integration.get_configuration_status()
        api_logger.info(
            "Integration connection test",
            extra={
                "source": source,
                "jira_connected": connection_results["jira"].get("connected", False),
                "allure_connected": connection_results["allure"].get("connected", False)
            }
        )
        return TestConnectionResponse(
            jira=connection_results["jira"],
            allure=connection_results["allure"],
            configuration_status=config_status
        )
    except Exception as e:
        api_logger.error(f"Error testing connections: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error testing connections: {str(e)}"
        )
@router.get("/configuration-status")
async def get_configuration_status():
    try:
        integration = DefectIntegration()
        config_status = integration.get_configuration_status()
        return {
            "status": "ok",
            "configuration": config_status,
            "instructions": {
                "jira": {
                    "url_required": True,
                    "auth_options": [
                        "Option 1: jira_email + jira_token (API Token) - для Jira Cloud",
                        "Option 2: jira_token (Bearer token) - для Jira Server/Data Center"
                    ],
                    "how_to_get_token": "Jira Cloud: Settings > Security > API tokens > Create API token"
                },
                "allure": {
                    "url_required": True,
                    "token_required": True,
                    "how_to_get_token": "Allure TestOps: User Settings > API Tokens > Generate new token"
                }
            }
        }
    except Exception as e:
        api_logger.error(f"Error getting configuration status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting configuration status: {str(e)}"
        )