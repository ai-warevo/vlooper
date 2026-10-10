"""Module documentation."""

import argparse
import re
import sys
from pathlib import Path

IGNORE_FILES = {
    Path("src/analyze_unused.py"),
    Path("src/check.py"),
    Path("src/vlooper/__main__.py"),
}

# Common lifecycle methods used by frameworks like Textual or FastAPI/Flask
FRAMEWORK_METHODS = {
    "compose",
    "on_mount",
    "on_unmount",
    "action_quit",
    "render",
    "on_click",
}


def get_all_py_files(root_dir):
    """Find all Python files in the given directory, excluding common ignore directories."""
    py_files = []
    exclude_dirs = {".git", "__pycache__", ".venv", "venv"}
    for path in Path(root_dir).rglob("*.py"):
        if not any(part in exclude_dirs for part in path.parts):
            py_files.append(path)
    return py_files


def get_module_name(file_path, src_root):
    """Convert a file path to a dot-separated module name."""
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
    """Extract all function and class definitions from a file."""
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
    """Extract environment variable names from a .env-style file."""
    env_vars = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*=", line)
                if match:
                    env_vars.add(match.group(1))
    except Exception as e:
        print(f"Error reading {path}: {e}")
    return env_vars


def get_used_env_vars(file_to_content):
    """Detect environment variable usage from file contents using regex patterns."""
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


def find_unused_files(all_py_files, file_to_content, src_root):
    """Identify Python files that are not imported by any other file."""
    mod_to_file = {
        get_module_name(f, src_root): f
        for f in all_py_files
        if f.is_relative_to(src_root) and get_module_name(f, src_root)
    }

    unused_files = []
    for mod, file_path in mod_to_file.items():
        if (
            file_path.name == "__init__.py"
            or file_path in IGNORE_FILES
            or "tests/" in str(file_path)
        ):
            continue

        is_imported = False
        file_name_no_ext = file_path.stem
        pattern_full = r"\b" + re.escape(mod) + r"\b"
        pattern_file = r"\b" + re.escape(file_name_no_ext) + r"\b"

        for other_file, content in file_to_content.items():
            if other_file != file_path:
                for line in content.splitlines():
                    if line.strip().startswith(("import ", "from ")) and (
                        re.search(pattern_full, line) or re.search(pattern_file, line)
                    ):
                        is_imported = True
                        break
            if is_imported:
                break

        if not is_imported:
            unused_files.append(file_path)
    return unused_files


def find_unused_definitions(all_py_files, file_to_content, known_used_names):
    """Identify function and class definitions that are not referenced elsewhere."""
    all_defs = []
    for f in all_py_files:
        for d in get_definitions(f):
            d["file"] = f
            all_defs.append(d)

    unused_defs = []
    for d in all_defs:
        if "tests/" in str(d["file"]):
            continue

        name, is_used = d["name"], False

        if name in known_used_names:
            is_used = True

        if not is_used:
            pattern = r"\b" + re.escape(name) + r"\b"

            for content in file_to_content.values():
                lines = content.splitlines()
                for i, line in enumerate(lines):
                    if (
                        (i + 1) != d["line"]
                        and not line.strip().startswith("#")
                        and re.search(pattern, line)
                    ):
                        is_used = True
                        break
                if is_used:
                    break

        if not is_used:
            unused_defs.append(d)
    return unused_defs


def check_env_vars(file_to_content, cwd):
    """Check for environment variables defined in .env files that are not used in the code."""
    defined_env_vars = set()
    for env_file in [cwd / ".env", cwd / ".env.example"]:
        if env_file.exists():
            defined_env_vars.update(get_env_vars_from_file(env_file))

    if not defined_env_vars:
        print("No .env or .env.example file found to analyze.")
        return False, set()

    used_env_vars = get_used_env_vars(file_to_content)
    unused_env_vars = defined_env_vars - used_env_vars
    return True, unused_env_vars


def get_known_used_names(cwd):
    """Gather names that are known to be used (e.g., from pyproject.toml or frameworks)."""
    known_used = set(FRAMEWORK_METHODS)

    # Check pyproject.toml for script entry points
    pyproject_path = cwd / "pyproject.toml"
    if pyproject_path.exists():
        try:
            content = pyproject_path.read_text(encoding="utf-8")
            # Look for the [project.scripts] section
            script_section = re.search(
                r"\[project\.scripts\](.*?)(?=\n\[|$)", content, re.DOTALL
            )
            if script_section:
                # Extract function names from "name = 'module:function'" patterns
                pattern = r'^\s*[^=]+=\s*[\'"][\w\.]+:([\w]+)[\'"]'
                entries = re.findall(pattern, script_section.group(1), re.MULTILINE)
                known_used.update(entries)
        except Exception as e:
            print(f"Warning: Could not parse pyproject.toml for scripts: {e}")

    return known_used


def _print_results(label, items, formatter=None):
    """Helper to print results."""
    print(f"\n[?] Potential Unused {label}:")
    if not items:
        print("None found.")
        return False
    for item in (
        sorted(items, key=lambda x: (str(x["file"]), x["line"]))
        if formatter
        else sorted(items)
    ):
        if formatter:
            print(f"  - {formatter(item)}")
        else:
            print(f"  - {item}")
    return True


def analyze():
    """Main orchestration function for the analysis tool."""
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

    cwd, src_root = Path("."), Path(".") / "src"
    if not src_root.exists():
        print("Error: src directory not found.")
        sys.exit(1)

    known_used_names = get_known_used_names(cwd)

    all_py_files = get_all_py_files(cwd)
    file_to_content = {}
    for f in all_py_files:
        try:
            with open(f, "r", encoding="utf-8") as file:
                file_to_content[f] = file.read()
        except Exception as e:
            print(f"Error reading {f}: {e}")

    any_unused = False
    if _print_results(
        "Files", find_unused_files(all_py_files, file_to_content, src_root)
    ):
        any_unused = True

    if _print_results(
        "Definitions",
        find_unused_definitions(all_py_files, file_to_content, known_used_names),
        lambda d: f"{d['type'].capitalize()} '{d['name']}' in {d['file']} (line {d['line']})",
    ):
        any_unused = True

    if args.check_env_vars:
        print("\n[?] Potential Unused Environment Variables:")
        has_env, unused_ev = check_env_vars(file_to_content, cwd)
        if has_env:
            if not unused_ev:
                print("None found.")
            else:
                for var in sorted(unused_ev):
                    print(f"  - {var}")
                any_unused = True

    if args.exit_on_error and any_unused:
        sys.exit(1)


if __name__ == "__main__":
    analyze()
