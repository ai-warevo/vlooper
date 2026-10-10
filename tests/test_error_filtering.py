from vlooper.core.error_handler import (
    filter_ignored_lines,
    clean_snippet,
    truncate_output,
)


def test_filter_ignored_lines():
    """
    Test that lines matching .gitignore patterns are removed from the text.
    """
    # Based on the project's .gitignore:
    # .pytest_cache/ is ignored
    # __pycache__/ is ignored
    # .venv is ignored
    # .env is ignored

    input_text = (
        "Important error message\n"
        "__pycache__/\n"
        "some_valid_path/file.py\n"
        ".venv\n"
        ".pytest_cache/\n"
        ".env\n"
        "end of message"
    )

    expected_output = (
        "Important error message\n" + "some_valid_path/file.py\n" + "end of message"
    )

    result = filter_ignored_lines(input_text)

    # We use strip() to avoid issues with trailing newlines during comparison
    assert result.strip() == expected_output.strip()


def test_filter_ignored_lines_empty():
    """Test filtering empty or whitespace-only strings."""
    assert filter_ignored_lines("") == ""
    assert filter_ignored_lines("   ") == "   "


def test_integration_with_cleaning_pipeline():
    """
    Test the full pipeline: truncate -> clean -> filter.
    This simulates what happens in the AILoop.error_handling logic.
    """
    raw_error = (
        "Error at /absolute/path/to/file.py:123\n"
        "Something went wrong!\n"
        "__pycache__/\n"
        ".venv\n"
        "Traceback (most recent call last):\n"
        '  File "main.py", line 10, in <module>\n'
        "    run()\n"
    )

    # 1. Truncate
    step1 = truncate_output(raw_error, lines=5)

    # 2. Clean (removes paths and line numbers as implemented in clean_snippet)
    step2 = clean_snippet(step1)

    # 3. Filter (removes git-ignored lines)
    step3 = filter_ignored_lines(step2)

    # Check that the ignored lines are gone
    assert "__pycache__/" not in step3
    assert ".venv" not in step3
    # Check that paths were cleaned by clean_snippet
    assert "/absolute/path/to/file.py:123" not in step3
