"""Скрипт для запуска всех линтеров и проверок одной командой."""

import subprocess
import sys


def run_command(command: list[str]) -> int:
    """Запускает системную команду и возвращает её код возврата."""
    print(f"▶️ Запуск: {' '.join(command)}...")
    result = subprocess.run(command, check=False)
    if result.returncode == 0:
        print("✅ Успешно!\n")
    else:
        print(f"❌ Ошибка! Код возврата: {result.returncode}\n")
    return result.returncode


def main() -> None:
    """Последовательно запускает весь стек проверок кода."""
    commands = [
        ["black", "--check", "src", "tests"],
        ["ruff", "check", "src", "tests"],
        ["mypy", "src", "tests"],
        ["pylint", "src"],
        ["pylint", "--disable=C0114,C0115,C0116,W0621,W0212,R0801", "tests"],
    ]

    has_errors = False
    for cmd in commands:
        if run_command(cmd) != 0:
            has_errors = True

    if has_errors:
        print("🚨 Некоторые проверки провалены!")
        sys.exit(1)
    else:
        print("🎉 Все проверки успешно пройдены! Код идеален. ✨")


if __name__ == "__main__":
    main()