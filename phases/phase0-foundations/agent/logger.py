import structlog
import logging
from agent.config import env_settings

def setup_logging():
    """Configure structlog for JSON logging with bound context variables."""
    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True
    )

def get_logger(run_id: str):
    """Returns a logger pre-bound with the given run_id."""
    # Ensure it's configured once
    setup_logging()
    return structlog.get_logger().bind(run_id=run_id)
