import os
from typing import Any
from ..framework.context import TaskContext
from ..framework.types import Middleware, NextFn

class AuthError(Exception):
    """Raised when required authentication tokens are missing."""
    pass

class GitHubAuthCheckMiddleware:
    """
    A middleware that proactively validates the existence of necessary 
    authentication tokens before allowing the pipeline to proceed 
    with integration-heavy steps.
    """

    def __call__(self, ctx: TaskContext, next_fn: NextFn) -> None:
        # Check for GitHub Token in environment variables
        if not os.environ.get("GH_TOKEN"):
            error_msg = "Authentication error: 'GH_TOKEN' environment variable is not set."
            ctx.is_aborted = True
            ctx.error = AuthError(error_msg)
            return

        # If token exists, proceed with the next layer in the pipeline.
        next_fn()
