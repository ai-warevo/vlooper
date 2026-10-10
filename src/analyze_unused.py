import argparse
import re
import sys
from pathlib import Path


def get_all_py_files(root_dir):
    py_files = []
    exclude_dirs = {".git", "__pycache__", ".venv", "venv"}
    for path in Path(root_dir).rglob("*.py"):
        if not any(part in exclude_dirs for part in path.parts):
            py_files.append(path)
    return py_files


def get_module_name(file_path, src_root):
    try:
        rel_path = file_path.relative_to(src_root)
        parts = list(rel_path.parts)
        if parts[-1] == "__init__.py":
            parts.pop()
        else:
            parts[-1] = parts[-1].replace(".py", "")
        return ".".join(parts)
    except ValueError:
        return None


def get_definitions(file_path):
    defs = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                match = re.search(r"^\s*(def|class)\s+([a-zA-Z_][a-zA-Z0-9_]*)", line)
                if match:
                    kind, name = match.groups()
                    defs.append({"name": name, "type": kind, "line": i + 1})
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return defs


def get_env_vars_from_file(path):
    env_vars = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Typical .env format is KEY=VALUE
                match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*=", line)
                if match:
                    env_vars.add(match.group(1))
    except Exception as e:
        print(f"Error reading {path}: {e}")
    return env_vars


def get_used_env_vars(file_to_content):
    used_vars = set()
    patterns = [
        re.compile(r"os\.getenv\(\s*['\"]([^'\"]+)['\"]\s*\)"),
        re.compile(r"os\.environ\.get\(\s*['\"]([^'\"]+)['\"].*?\)"),
        re.compile(r"os\.environ\[['\"]([^'\"]+)['\"]\]"),
        re.compile(r"environ\[['\"]([^'\"]+)['\"]\]"),
        re.compile(r"getenv\(\s*['\"]([^'\"]+)['\"]\s*\)"),
    ]
    for content in file_to_content.values():
        for pattern in patterns:
            matches = pattern.findall(content)
            for match in matches:
                used_vars.add(match)
    return used_vars


def analyze():
    parser = argparse.ArgumentParser(
        description="Analyze unused Python files and definitions."
    )
    parser.add_argument(
        "--exit-on-error",
        action="store_true",
        help="Exit with status 1 if unused code is found",
    )
    parser.add_argument(
        "--check-env-vars",
        action="store_true",
        help="Check for unused environment variables from .env files",
    )
    args = parser.parse_args()

    cwd = Path(".")
    src_root = cwd / "src"
    if not src_root.exists():
        print("Error: src directory not found.")
        sys.exit(1)

    all_py_files = get_all_py_files(cwd)
    print(f"Found {len(all_py_files)} python files.")

    file_to_content = {}
    for f in all_py_files:
        try:
            with open(f, "r", encoding="utf-8") as file:
                file_to_content[f] = file.read()
        except Exception as e:
            print(f"Error reading {f}: {e}")

    mod_to_file = {}
    for f in all_py_files:
        if f.is_relative_to(src_root):
            mod_name = get_module_name(f, src_root)
            if mod_name:
                mod_to_file[mod_name] = f

    unused_files = []
    for mod, file_path in mod_to_file.items():
        if file_path.name == "__init__.py":
            continue

        is_imported = False
        for other_file, content in file_to_content.items():
            if other_file == file_path:
                continue

            lines = content.splitlines()
            for line in lines:
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")):
                    pattern = r"\b" + re.escape(mod) + r"\b"
                    if re.search(pattern, line):
                        is_imported = True
                        break
            if is_imported:
                break

        if not is_imported:
            unused_files.append(file_path)

    all_defs = []
    for f in all_py_files:
        defs = get_definitions(f)
        for d in defs:
            d["file"] = f
            all_defs.append(d)

    unused_defs = []
    for d in all_defs:
        name = d["name"]
        is_used = False
        pattern = r"\b" + re.escape(name) + r"\b"

        for other_file, content in file_to_content.items():
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if other_file == d["file"] and (i + 1) == d["line"]:
                    continue
                if line.strip().startswith("#"):
                    continue
                if re.search(pattern, line):
                    is_used = True
                    break
            if is_used:
                break

        if not is_used:
            unused_defs.append(d)

    any_unused = False

    print("\n[?] Potential Unused Files:")
    if not unused_files:
        print("None found.")
    else:
        for f in sorted(unused_files):
            print(f"  - {f}")
        any_unused = True

    print("\n[?] Potential Unused Definitions:")
    if not unused_defs:
        print("None found.")
    else:
        sorted_defs = sorted(unused_defs, key=lambda x: (str(x["file"]), x["line"]))
        for d in sorted_defs:
            print(
                f"  - {d['type'].capitalize()} '{d['name']}' in {d['file']} (line {d['line']})"
            )
        any_unused = True

    if args.check_env_vars:
        print("\n[?] Potential Unused Environment Variables:")
        defined_env_vars = set()
        # Check .env and .env.example in the current directory
        for env_file in [cwd / ".env", cwd / ".env.example"]:
            if env_file.exists():
                defined_env_vars.update(get_env_vars_from_file(env_file))

        if not defined_env_vars:
            print("No .env or .env.example file found to analyze.")
        else:
            used_env_vars = get_used_env_vars(file_to_content)
            unused_env_vars = defined_env_vars - used_env_vars
            if not unused_env_vars:
                print("None found.")
            else:
                for var in sorted(unused_env_vars):
                    print(f"  - {var}")
                any_unused = True

    if args.exit_on_error and any_unused:
        sys.exit(1)


if __name__ == "__main__":
    analyze()
