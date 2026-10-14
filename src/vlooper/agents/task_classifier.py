from typing import Any, Dict
from vlooper.core.framework.context import TaskContext
from vlooper.infra.logger import get_logger
from vlooper.clients.opencode_client import OpencodeClient

logger = get_logger(__name__)


def task_classifier_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: task_classifier
    Task: Classifies whether the issue is a 'feature' or a 'bug'.
    """
    logger.info("[TASK_CLASSIFIER] Starting classification...")

    # The brief contains instructions and the context via input_data (from the previous step)
    input_data = brief.get("raw_input", {})
    title = input_data.get("title") or ctx.issue_title or "No title"
    body = input_data.get("body") or ctx.issue_body or "No body"

    classification_prompt = (
        "Analyze the following GitHub issue and classify it as either 'feature' or 'bug'. "
        "A 'feature' is a new piece of functionality or requirement. "
        "A 'bug' is a fix for existing broken behavior, an error, or unintended side effect.\n\n"
        f"Title: {title}\n"
        f"Body: {body}\n\n"
        "Return ONLY the single word 'feature' or 'bug'."
    )

    client = OpencodeClient()
    try:
        result, err = client.run(classification_prompt)
        if err:
            logger.error("[TASK_CLASSIFIER] Error during classification: %s", err)
            return {"status": "failed", "error": err}

        if not result:
            return {"status": "failed", "error": "Empty response from LLM"}

        classification = result.strip().lower()
        
        # Check for specific keywords in the response to be robust
        if "feature" in classification and "bug" not in classification:
            decision = "feature"
        elif "bug" in classification:
            decision = "bug"
        else:
            # Fallback/Safety
            logger.warning("[TASK_CLASSIFIER] Unexpected output '%s', defaulting to 'bug'", result)
            decision = "bug"

        logger.info("[TASK_CLASSIFIER] Classification decision: %s", decision)
        return {
            "status": "success",
            "output": {"task_type": decision}
        }

    except Exception as e:
        logger.exception("[TASK_CLASSIFIER] Unexpected error")
        return {"status": "failed", "error": str(e)}
