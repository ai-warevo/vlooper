"""Service for AI-powered tasks like generating commit messages."""

import os
from vlooper.config import config
from vlooper.infra.logger import get_logger
from vlooper.infra.utils import run_command
from vlooper.clients.git_client import has_uncommitted_changes

logger = get_logger(__name__)


def generate_commit_message(repo_dir: str, issue_number: int) -> str:
    """Generates a concise commit message based on git diff using an LLM."""
    if not has_uncommitted_changes(repo_dir):
        return f"fix: automated fix for issue #{issue_number}"

    logger.info("🤖 Generating AI-powered commit message...")

    # 1. Get the git diff
    stdout, err = run_command(["git", "diff"], cwd=repo_dir)
    if err:
        logger.error("Failed to get git diff: %s", err)
        return f"fix: automated fix for issue #{issue_number}"

    if not stdout or not stdout.strip():
        return f"fix: automated fix for issue #{issue_number}"

    # 2. Prepare the prompt
    prompt = (
        f"Write ONLY a single-line, concise commit message in conventional commits format "
        f"for the following git diff. Do not include any explanations or extra text:\n\n"
        f"{stdout[:4000]}"  # Limit diff size to avoid huge prompts
    )

    # 3. Call Opencode agent
    # We'll use 'opencode run --model <model> "<prompt>"'
    cmd = ["opencode", "run", "--model", config.model_cfg.model, prompt]

    try:
        logger.debug("Executing AI command: %s", " ".join(cmd))
        # We use a slightly higher timeout for LLM calls if needed
        result, err = run_command(cmd, cwd=repo_dir, timeout=config.timeouts.execution_timeout)

        if err:
            logger.warning("AI commit message generation failed: %s. Using fallback.", err)
            return f"fix: automated fix for issue #{issue_number}"

        # 4. Clean up the result
        # The agent might output more than just one line, so we take the first non-empty line
        lines = [line.strip() for line in result.splitlines() if line.strip()]
        if lines:
            # Take the first line as the commit message
            commit_msg = lines[0]
            # Remove common prefixes if the agent added them like "Commit message: ..."
            if ":" in commit_msg and len(commit_msg.split(":")[0]) < 20:
                commit_msg = commit_msg.split(":", 1)[1].strip()

            logger.info("✨ Generated AI commit message: %s", commit_msg)
            return commit_msg

    except Exception as e:
        logger.error("Error during AI commit message generation: %s", e)

    return f"fix: automated fix for issue #{issue_number}"
