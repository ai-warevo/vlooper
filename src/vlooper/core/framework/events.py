"""Module documentation."""

from enum import Enum


class EventName(str, Enum):
    """Centralized registry of all system-wide event names."""

    # Task Life Cycle Events
    TASK_PICKED_UP = "task:picked_up"
    TASK_FINISHED = "task:finished"

    # Git/Repository Events
    GIT_ISOLATED = "git:isolated"

    # Test Harness Events
    HARNESS_TEST_PASSED = "harness:test_passed"
    HARNESS_FIXING_CODE = "harness:fixing_code"

    # GitHub Events
    GITHUB_PR_CREATED = "github:pr_created"
