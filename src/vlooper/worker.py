import os
import subprocess
import json
from vlooper.config import config
from vlooper.database import Database

def run_command(cmd, cwd=None, timeout=None):
    """Run a command with an optional timeout."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)
        if res.returncode != 0:
            error_msg = f"Command failed: {' '.join(cmd)}\nStderr: {res.stderr}"
            return None, error_msg
        return res.stdout.strip(), None
    except subprocess.TimeoutExpired:
        return None, f"Command timed out after {timeout}s: {' '.join(cmd)}"
    except Exception as e:
        return None, str(e)

class Worker:
    def __init__(self, db: Database):
        self.db = db

    def process_next_task(self):
        tasks = self.db.get_pending_tasks()
        if not tasks:
            return False

        # Pick the first pending task
        task = tasks[0]
        task_id = task['id']

        print(f"🛠 Picking up task #{task_id}: {task['task_type']} in {task['repo_full_name']} (branch: {task['branch_name']})")
        
        if not self.db.claim_task(task_id):
            return False  # Someone else claimed it

        try:
            success = self._execute_task(task)
            if success:
                self.db.complete_task(task_id)
                print(f"✅ Task #{task_id} completed successfully.")
            else:
                raise Exception("Task execution failed (see logs).")
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Task #{task_id} failed: {error_msg}")
            self.db.fail_task(task_id, error_msg)
            return False

        return True

    def _execute_task(self, task):
        repo_full_name = task['repo_full_name']
        branch_name = task['branch_name']
        task_type = task['task_type']
        
        # Extract repo short name
        repo_short_name = repo_full_name.split('/')[-1]

        # Get context for the AI agent
        context = self._get_context(task, repo_full_name)
        if not context:
            return False

        commit_msg = f"{'refactor: ' if task_type == 'PR' else 'fix: '} #{self._get_issue_number(task)}"
        if task_type == "ISSUE":
            try:
                num = branch_name.split('-')[-1]
                commit_msg = f"fix #{num}"
            except:
                commit_msg = "fix issue"
        else:
             commit_msg = f"refactor PR on {branch_name}"

        # 1. Setup workspace
        base_dir = os.path.expanduser(config.workspace_base_dir)
        os.makedirs(base_dir, exist_ok=True)
        repo_dir = os.path.join(base_dir, repo_short_name)

        if not os.path.exists(repo_dir):
            print(f"📦 Cloning repository {repo_full_name}...")
            stdout, err = run_command(["gh", "repo", "clone", repo_full_name, repo_short_name], cwd=base_dir)
            if err: raise Exception(err)

        # 2. Reset to main and update
        print("🧹 Resetting to main...")
        stdout, err = run_command(["git", "checkout", "main"], cwd=repo_dir, timeout=config.execution_timeout)
        if err: raise Exception(err)

        stdout, err = run_command(["git", "pull", "origin", "main"], cwd=repo_dir, timeout=config.execution_timeout)
        if err: 
            print("⚠️ Could not pull origin main, proceeding anyway.")

        # 3. Checkout/Create task branch
        print(f"🌿 Preparing branch {branch_name}...")
        stdout, err = run_command(["git", "checkout", "-B", branch_name], cwd=repo_dir, timeout=config.execution_timeout)
        if err: raise Exception(err)

        if task_type == "PR":
             print(f"📥 Pulling remote branch {branch_name}...")
             stdout, err = run_command(["git", "pull", "origin", branch_name], cwd=repo_dir, timeout=config.execution_timeout)
             if err: raise Exception(err)

        # 4. Run Opencode
        print(f"🚀 Running OpenCode...")
        opencode_cmd = ["opencode", "--model", config.model, "--run-test", config.test_command, context]
        stdout, err = run_command(opencode_cmd, cwd=repo_dir, timeout=config.execution_timeout)
        if err: raise Exception(err)

        # 5. Commit and Push
        print(f"💾 Committing changes...")
        commit_cmd = ["git", "-c", "user.name=AI OpenCode Bot", "-c", "user.email=ai-bot@://github.com", "commit", "-am", commit_msg]
        stdout, err = run_command(commit_cmd, cwd=repo_dir, timeout=config.execution_timeout)
        if err: raise Exception(err)

        print(f"📤 Pushing to origin...")
        push_cmd = ["git", "push", "origin", branch_name]
        stdout, err = run_command(push_cmd, cwd=repo_dir, timeout=config.execution_timeout)
        if err: raise Exception(err)

        # 6. Create PR if it was an issue
        if task_type == "ISSUE":
            print(f"📢 Creating Pull Request...")
            pr_create_cmd = ["gh", "pr", "create", "--repo", repo_full_name, "--title", f"Fix for {branch_name}", "--body", "Automated fix by vLooper agent."]
            stdout, err = run_command(pr_create_cmd, cwd=repo_dir, timeout=config.execution_timeout)
            if err: raise Exception(err)

        return True

    def _get_context(self, task, repo_full_name):
        num = task['branch_name'].split('-')[-1] if task['task_type'] == 'ISSUE' else None
        
        if task['task_type'] == 'ISSUE':
            try:
                view_cmd = ["gh", "issue", "view", str(num), "--repo", repo_full_name, "--json", "title,body"]
                res, err = run_command(view_cmd)
                if err: return None
                issue_data = json.loads(res)
                title = issue_data['title']
                body = issue_data['body'] or ""

                comments_cmd = ["gh", "issue", "view", str(num), "--repo", repo_full_name, "--json", "comments"]
                res_c, err_c = run_command(comments_cmd)
                if err_c: 
                    comments_text = ""
                else:
                    comments = json.loads(res_c).get('comments', [])
                    comments_text = "\n".join([f"Комментарий от {c['author']['login']}: {c['body']}" for c in comments])

                return f"Задача #{num} в репозитории {repo_full_name}: {title}\nОписание:\n{body}\n\nИстория переписки:\n{comments_text}"
            except Exception as e:
                print(f"Error getting issue context: {e}")
                return None
        else: # PR
            try:
                branch = task['branch_name']
                list_pr_cmd = ["gh", "pr", "list", "--repo", repo_full_name, "--head", branch, "--json", "number,title,body,comments,reviews"]
                res_p, err_p = run_command(list_pr_cmd)
                if err_p or not res_p: return None
                prs = json.loads(res_p)
                if not prs: return None
                pr = prs[0]
                
                num = pr['number']
                title = pr['title']
                body = pr['body'] or ""

                review_text = ""
                for r in pr.get('reviews', []):
                    if r.get('body'):
                        review_text += f"Ревью от {r['author']['login']}: {r['body']}\n"
                for c in pr.get('comments', []):
                    review_text += f"Замечание от {c['author']['login']}: {c['body']}\n"

                if "Исправлено ботом" in review_text:
                    return None 

                return f"Доработка по Pull Request #{num} в репозитории {repo_full_name} (ветка {branch}).\nЗамечания к коду:\n{review_text}\n\nОписание PR:\n{body}"
            except Exception as e:
                print(f"Error getting PR context: {e}")
                return None

    def _get_issue_number(self, task):
        if task['task_type'] == 'ISSUE':
             try:
                 return task['branch_name'].split('-')[-1]
             except:
                 return "unknown"
        return "PR"
