"""Custom exceptions for vLooper."""


class VLooperError(Exception):
    """Base exception for vLooper."""


class GitHubCLIFailure(VLooperError):
    """Raised when a GitHub CLI command fails."""
