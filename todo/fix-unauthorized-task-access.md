# Task: Implement Author Whitelist for Task Ingestion
**Vulnerability Type:** Broken Access Control (CWE-284) / Unauthorized Resource Usage
**Severity:** Medium
**Target Files:** `src/vlooper/config/git.py`, `src/vlooper/core/scanner.py`

## Context & Description
Currently, the vLooper scanner picks up *any* open issue or Pull Request assigned to the bot, regardless of who authored it. This allows any GitHub user to trigger the automated execution pipeline by simply assigning an issue to the bot. This can lead to:
1. **Resource Exhaustion:** Malicious users could flood the system with tasks.
2. **Cost Exploitation:** Unauthorized usage of expensive AI models (Opencode).

Implementing a "Whitelist" (Authorized Users list) ensures that the daemon only processes tasks created by trusted administrators or specific team members.

## Insecure Code Reference
```python
# src/vlooper/core/scanner.py

def _scan_items(self, is_pr: bool):
    # ... 
    items, err = get_assigned_items(
        org_name=config.git.org_name,
        bot_username=config.git.bot_username,
        is_pr=is_pr
    )
    # ... items are processed without checking the author
```

## Remediation Instruction (Prompt for the Developer Agent)
Act as an expert software engineer. Implement a whitelist-based authorization mechanism for task ingestion.

Follow these strict constraints:
1. **Update Configuration:** 
   * Add an `authorized_users: list[str]` field to the `GitConfig` class in `src/vlooper/config/git.py`.
   * Ensure this can be populated via the `AUTHORIZED_USERS` environment variable (comma-separated string).
2. **Optimize Scanning:** 
   * Modify the `get_assigned_items` call in `src/vlooper/core/scanner.py` (or its underlying service) to include the `author` field in the GitHub CLI `--json` parameter. This avoids making extra API calls for every item found.
3. **Implement Filtering:** 
   * In `src/vlooper/core/scanner.py`, within the `_process_scan_item` method, check if the author of the issue/PR (obtained from the search results) is present in the `config.git.authorized_users` list.
   * If the author is NOT authorized, log a warning and skip adding the task to the database.
4. **Do not alter business logic** for existing authorized users.
5. Ensure that after your changes, running the repository's `./test.sh` script passes successfully with an `exit 0` status.

## Expected Secure Code Pattern
```python
# In scanner.py
for item in items:
    author_login = item.get("author", {}).get("login")
    if author_login not in config.git.authorized_users:
        logger.warning("Skipping unauthorized task from user: %s", author_login)
        continue
    
    self._process_scan_item(item, ...)
```
