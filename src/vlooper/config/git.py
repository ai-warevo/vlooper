"""Module docstring."""

import os
from dataclasses import dataclass, field


@dataclass
class GitConfig:
    """Git related configuration."""

    org_name: str = field(
        default_factory=lambda: os.environ.get("ORG_NAME", "ai-warevo")
    )
    bot_username: str = field(
        default_factory=lambda: os.environ.get("BOT_USERNAME", "your_bot_login")
    )
    git_user_name: str = field(
        default_factory=lambda: os.environ.get("GIT_USER_NAME", "AI OpenCode Bot")
    )
    git_user_email: str = field(
        default_factory=lambda: os.environ.get("GIT_USER_EMAIL", "ai-bot@://github.com")
    )
    gh_token: str | None = field(
        default_factory=lambda: os.environ.get("GH_TOKEN", None)
    )
    authorized_users: list[str] = field(
        default_factory=lambda: [
            u.strip()
            for u in os.environ.get("AUTHORIZED_USERS", "").split(",")
            if u.strip()
        ]
    )
