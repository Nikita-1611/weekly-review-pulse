import traceback
from functools import wraps
from typing import Callable, Any
from agent.logger import get_logger
from orchestrator.state_manager import StateManager

def audit_step(step_name: str, success_status: str):
    """
    Decorator that wraps pipeline steps to automatically log completion 
    and catch/log errors to the state manager.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # We assume run_id is always passed to the pipeline steps
            run_id = kwargs.get('run_id')
            if not run_id:
                raise ValueError("run_id must be provided as a kwarg to audited steps.")
                
            logger = get_logger(run_id)
            logger.info(f"Starting step: {step_name}")
            
            try:
                result = func(*args, **kwargs)
                
                # Mark step as successful in DB
                StateManager.update_run_status(run_id, success_status)
                logger.info(f"Completed step: {step_name}. State -> {success_status}")
                
                return result
                
            except Exception as e:
                error_trace = traceback.format_exc()
                logger.error(f"Failed at step: {step_name}", error=str(e))
                
                # Update DB state to failed and log the trace
                StateManager.update_run_status(run_id, "failed", error_log=error_trace)
                
                # Re-raise to stop the pipeline
                raise

        return wrapper
    return decorator
