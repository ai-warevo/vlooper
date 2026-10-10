from ..framework.pipeline import TaskPipeline
from .middleware_retry_limit import RetryLimitMiddleware
from .step_run_tests import run_repository_tests
from .step_apply_fix import apply_ai_fix

def configure_loop_pipeline(pipeline: TaskPipeline) -> TaskPipeline:
    """
    Declaratively configures the task pipeline for the autonomous 
    'Write -> Test -> Fix' cycle.
    
    The configuration follows this structure:
    - Middleware: RetryLimitMiddleware (Wraps all steps in a retry loop)
    - Step: run_repository_tests (Executes tests and captures results)
    - Step: apply_ai_fix (If tests fail, triggers AI attempt to fix code)

    Returns:
        The configured TaskPipeline instance.
    """
    return (
        pipeline
        .use(RetryLimitMiddleware(max_attempts=5))
        .add_step(run_repository_tests)
        .add_step(apply_ai_fix)
    )
