#!/usr/bin/env python3
import os
import sys
import json
import subprocess

# --- КОНФИГУРАЦИЯ ---
ORG_NAME = "ai-warevo"       # Название твоей организации на GitHub
BOT_USERNAME = "логин_твоего_бота"
MODEL = "ollama/gemma"       # Твоя локальная модель
TEST_COMMAND = "./test.sh"
# ---------------------

def run_command(cmd, cwd=None):
    """Безопасный запуск shell-команд"""
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if res.returncode != 0:
        print(f"Ошибка при выполнении: {' '.join(cmd)}\n{res.stderr}")
        return None
    return res.stdout.strip()

def process_work():
    print(f"🤖 Сканирование задач для ИИ-агента в организации {ORG_NAME}...")
    
    # 1. Поиск всех назначенных ISSUES во ВСЕЙ организации через поисковый движок GitHub CLI
    search_issues_cmd = [
        "gh", "search", "issues", 
        f"org:{ORG_NAME}", f"assignee:{BOT_USERNAME}", "state:open", "type:issue",
        "--json", "number,title,body,repository"
    ]
    issues_json = run_command(search_issues_cmd)
    issues = json.loads(issues_json) if issues_json else []
    
    # 2. Поиск всех назначенных PULL REQUESTS во ВСЕЙ организации
    search_prs_cmd = [
        "gh", "search", "issues", 
        f"org:{ORG_NAME}", f"assignee:{BOT_USERNAME}", "state:open", "type:pr",
        "--json", "number,title,body,repository"
    ]
    prs_json = run_command(search_prs_cmd)
    prs = json.loads(prs_json) if prs_json else []

    # ОБРАБОТКА ISSUES
    for issue in issues:
        num = issue['number']
        title = issue['title']
        body = issue['body'] or ""
        # Извлекаем полное имя репозитория (например, "ai-warevo/calculator")
        repo_full_name = issue['repository']['nameWithOwner']
        repo_short_name = repo_full_name.split('/')[-1]
        
        # Собираем комментарии к конкретному репозиторию
        comments_json = run_command(["gh", "issue", "view", str(num), "--repo", repo_full_name, "--json", "comments"])
        comments_text = ""
        if comments_json:
            comments = json.loads(comments_json).get('comments', [])
            comments_text = "\n".join([f"Комментарий от {c['author']['login']}: {c['body']}" for c in comments])

        full_task_context = f"Задача #{num} в репозитории {repo_full_name}: {title}\nОписание:\n{body}\n\nИстория переписки:\n{comments_text}"
        
        print(f"🔥 Взят в работу Issue #{num} из репозитория {repo_full_name}")
        
        # Передаем имя репозитория в воркфлоу, чтобы бот знал, где именно клонировать/править код
        execute_opencode_workflow(repo_full_name, repo_short_name, f"issue-{num}", full_task_context, f"fix #{num}: {title}")
        
        # Снимаем с бота задачу
        run_command(["gh", "issue", "edit", str(num), "--repo", repo_full_name, "--remove-label", "ai-todo"])
        return 

    # ОБРАБОТКА PULL REQUESTS
    for pr in prs:
        num = pr['number']
        title = pr['title']
        repo_full_name = pr['repository']['nameWithOwner']
        repo_short_name = repo_full_name.split('/')[-1]
        
        # Чтобы узнать имя ветки для PR, запрашиваем детали конкретного PR
        pr_details_json = run_command(["gh", "pr", "view", str(num), "--repo", repo_full_name, "--json", "headRefName,comments,reviews"])
        if not pr_details_json: continue
        
        pr_data = json.loads(pr_details_json)
        branch = pr_data.get('headRefName')
        
        review_text = ""
        for r in pr_data.get('reviews', []):
            if r.get('body'):
                review_text += f"Ревью от {r['author']['login']}: {r['body']}\n"
        for c in pr_data.get('comments', []):
            review_text += f"Замечание от {c['author']['login']}: {c['body']}\n"

        if "Исправлено ботом" in review_text: 
            continue 

        full_task_context = f"Доработка по Pull Request #{num} в репозитории {repo_full_name} (ветка {branch}).\nЗамечания к коду:\n{review_text}"
        
        print(f"🛠 Взята доработка по PR #{num} из репозитория {repo_full_name}")
        execute_opencode_workflow(repo_full_name, repo_short_name, branch, full_task_context, f"refactor: правки по замечаниям к PR #{num}", is_pr=True)
        return

def execute_opencode_workflow(repo_full_name, repo_short_name, branch_name, context, commit_msg, is_pr=False):
    # Корневой путь, где бот локально хранит выкачанные проекты организации
    base_dir = os.path.expanduser("~/ai_agent/workspace")
    os.makedirs(base_dir, exist_ok=True)
    repo_dir = os.path.join(base_dir, repo_short_name)
    
    # Если репозиторий еще не склонирован локально — клонируем его
    if not os.path.exists(repo_dir):
        print(f"📦 Клонирование нового репозитория {repo_full_name}...")
        run_command(["gh", "repo", "clone", repo_full_name, repo_short_name], cwd=base_dir)
        
    # Переходим в рабочую директорию конкретного проекта
    run_command(["git", "checkout", "main"], cwd=repo_dir)
    run_command(["git", "pull", "origin", "main"], cwd=repo_dir)
    
    # Переключаемся на рабочую ветку задачи
    run_command(["git", "checkout", "-B", branch_name], cwd=repo_dir)
    if is_pr:
        run_command(["git", "pull", "origin", branch_name], cwd=repo_dir)
        
    # --- ВЫЗОВ OPENCODE (Harness & Loop) ---
    print(f"🚀 Запуск локального OpenCode цикла для проекта {repo_short_name}...")
    opencode_cmd = ["opencode", "--model", MODEL, "--run-test", TEST_COMMAND, context]
    subprocess.run(opencode_cmd, cwd=repo_dir)
    
    # Коммитим строго от лица ИИ-бота внутри этой папки
    run_command(["git", "-c", "user.name=AI OpenCode Bot", "-c", "user.email=ai-bot@://github.com", "commit", "-am", commit_msg], cwd=repo_dir)
    
    # Пушим изменения в облако
    run_command(["git", "push", "origin", branch_name], cwd=repo_dir)
    
    if not is_pr:
        # Создаем Pull Request для новой фичи
        run_command(["gh", "pr", "create", "--repo", repo_full_name, "--title", f"Фикс для {branch_name}", "--body", "Автоматический пулреквест от мульти-репозиторного OpenCode агента."], cwd=repo_dir)
        
    run_command(["git", "checkout", "main"], cwd=repo_dir)
    print(f"✅ Обработка проекта {repo_short_name} успешно завершена!")

if __name__ == "__main__":
    if not os.environ.get("GH_TOKEN"):
        print("❌ Ошибка: Переменная окружения GH_TOKEN не задана!")
        sys.exit(1)
    process_work()
