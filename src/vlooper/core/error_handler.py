"""Module for handling and summarizing errors encountered during execution."""

import re
from difflib import SequenceMatcher

from vlooper.config import config
from vlooper.logger import get_logger
from vlooper.utils import run_command

logger = get_logger(__name__)


def truncate_output(output: str, lines: int = 50) -> str:
    """Truncate output to the last N lines."""
    if not output:
        return ""
    output_lines = output.splitlines()
    if len(output_lines) > lines:
        return "\n".join(output_lines[-lines:])
    return output


def clean_snippet(snippet: str) -> str:
    """Remove noisy parts like file paths, line numbers, and IDs from snippets."""
    # Remove absolute paths (starting with /)
    snippet = re.sub(r"/[^ \n\t]+", "", snippet)
    # Remove relative paths and line numbers like "path/to/file.py:123:456"
    # or "path/to/file.py:123"
    snippet = re.sub(r":\d+(?::\d+)*", "", snippet)
    # Remove timestamps (e.g., 2023-10-07 12:00:00 or [12:00:00])
    snippet = re.sub(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", "", snippet)
    snippet = re.sub(r"\[?\d{2}:\d{2}:\d{2}\]?", "", snippet)
    # Remove hex addresses and UUIDs
    snippet = re.sub(r"0x[0-9a-fA-F]+", "", snippet)
    snippet = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "",
        snippet,
        flags=re.IGNORECASE,
    )
    # Remove other noise patterns like "(106/100)"
    snippet = re.sub(r"\(\d+/\d+\)", "", snippet)
    # Remove common words that might change slightly
    snippet = re.sub(r"on line \d+", "", snippet)
    # Normalize whitespace
    snippet = " ".join(snippet.split())
    return snippet.strip()


def get_error_summary(err_text: str) -> str:
    """Use an LLM to create a concise summary of the error."""
    if not err_text or len(err_text.strip()) < 5:
        return err_text

    # Truncate input for the LLM if it's too long
    truncated_err = truncate_output(err_text, lines=20)

    prompt = (
        "Summarize this error message in a single, concise sentence. "
        "Focus on the root cause "
        "(e.g., 'missing file', 'syntax error in X', 'type error in Y'). "
        "Do not include paths or line numbers.\n\n"
        f"{truncated_err}"
    )

    try:
        model = config.model.split("/")[-1]  # e.g., 'ollama/gemma' -> 'gemma'
        cmd = ["ollama", "run", model, prompt]
        stdout, _err = run_command(cmd, timeout=30)
        if stdout:
            return stdout.strip()
    except Exception as e:
        logger.warning(f"Error summarizing error: {e}")

    # Fallback to cleaning the snippet if LLM fails
    return clean_snippet(err_text)


def is_stuck(new_snip: str, last_err_snip: str | None) -> bool:
    """Check if two error snippets are semantically similar."""
    if last_err_snip is None:
        return False

    new_snip = clean_snippet(new_snip)
    last_err_snip = clean_snippet(last_err_snip)

    if not new_snip or not last_err_snip:
        return False

    similarity = SequenceMatcher(None, new_snip, last_err_snip).ratio()

    # Case 1: Very similar - definitely stuck
    if similarity >= 0.8:
        return True

    # Case 2: Very different - definitely not stuck (yet)
    if similarity < 0.4:
        return False

    # Case 3: Ambiguous - use LLM for a second opinion
    logger.info(f"Similarity is {similarity:.2f}, using LLM to decide if stuck...")
    llm_decision = ask_llm_if_stuck(new_snip, last_err_snip)

    if llm_decision is not None:
        return llm_decision

    # Fallback to similarity score if LLM fails or is inconclusive
    return similarity >= 0.6


def ask_llm_if_stuck(new_snip: str, last_err_snip: str) -> bool | None:
    """Asks the LLM to compare errors.

    Returns True/False if sure, or None if failed.
    """
    if not config.model.startswith("ollama/"):
        logger.warning("Model is not an Ollama model. Skipping LLM check.")
        return None

    try:
        prompt = build_stuck_prompt(new_snip, last_err_snip)
        model = config.model.split("/")[-1]

        cmd = ["ollama", "run", model, prompt]
        stdout, _err = run_command(cmd, timeout=30)

        if stdout:
            return parse_llm_stuck_response(stdout)

    except Exception as e:
        logger.warning(f"LLM stuck detection failed: {e}.")

    return None


def build_stuck_prompt(new_snip: str, last_err_snip: str) -> str:
    """Builds a structured prompt for the LLM."""
    return (
        f"Are these two error messages semantically the same (mean the same thing)?\n"
        f"Answer with only 'YES' or 'NO'.\n\n"
        f"Error 1: {new_snip}\n"
        f"Error 2: {last_err_snip}"
    )


def parse_llm_stuck_response(stdout: str) -> bool | None:
    """Parses LLM output safely using word boundaries to avoid false

    positives.
    """
    clean_resp = stdout.strip().upper().replace('"', "").replace("'", "")

    if re.search(r"\bYES\b", clean_resp):
        return True
    if re.search(r"\bNO\b", clean_resp):
        return False

    logger.warning(f"LLM returned ambiguous response: '{stdout.strip()}'")
    return None


def check_error_loop(summary, cleaned_snip, error_summaries) -> bool:
    """Check if the current error summary and snippet matches past failures closely."""
    for prev_summary, prev_snip in error_summaries:
        if (
            SequenceMatcher(None, summary, prev_summary).ratio() > 0.8
            and SequenceMatcher(None, cleaned_snip, prev_snip).ratio() > 0.8
        ):
            return True
    return False
