
import logging
import sys
from typing import Any, Dict
from shared.config.settings import settings
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    return logger
api_logger = get_logger("api_gateway")
worker_logger = get_logger("celery_worker")
agent_logger = get_logger("agents")
llm_logger = get_logger("llm_client")