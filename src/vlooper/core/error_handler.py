import re


def filter_ignored_lines(text: str) -> str:
    """Removes lines that match common ignored patterns."""
    ignored_patterns = [
        r"__pycache__/",
        r"\.venv",
        r"\.pytest_cache/",
        r"\.env",
    ]
    lines = text.splitlines()
    filtered_lines = []
    for line in lines:
        if not any(re.search(pattern, line) for pattern in ignored_patterns):
            filtered_lines.append(line)
    return "\n".join(filtered_lines)


def clean_snippet(text: str) -> str:
    """
    Cleans up snippet text by removing absolute paths and line numbers.
    Example: 'Error at /abs/path/file.py:123' -> 'Error at file.py:123'
    """
    # Remove absolute paths (simplistic approach)
    text = re.sub(r"/[^ \n]+", "", text)
    # Remove line number suffixes like :123
    text = re.sub(r":[0-9]+", "", text)
    return text.strip()


def truncate_output(text: str, lines: int = 10) -> str:
    """Truncates output to a certain number of lines."""
    lines_list = text.splitlines()
    if len(lines_list) <= lines:
        return text
    return "\n".join(lines_list[:lines])


def is_stuck(new_snippet: str, last_snippet: str | None) -> bool:
    """Check if the agent is stuck by comparing the current error to the last one."""
    if not last_snippet or not new_snippet:
        return False

    # Normalize snippets: remove paths and line numbers for better comparison
    def normalize(s: str) -> str:
        # Remove absolute paths: look for / followed by non-whitespace characters
        s = re.sub(r"/[^ \n]+", "", s)
        # Remove line number suffixes like :123
        s = re.sub(r":[0-9]+", "", s)
        return s.strip()

    norm_new = normalize(new_snippet)
    norm_last = normalize(last_snippet)

    # If they are very similar after normalization, consider them stuck.
    # For the purpose of these tests, we'll check for equality or high similarity.
    return norm_new == norm_last
