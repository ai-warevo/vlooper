import subprocess
import sys

def main():
    """Runs linters and formatters (ruff and black)."""
    print("🚀 Running project checks...")
    
    # Run Ruff (linting)
    print("\n--- Running Ruff ---")
    ruff_res = subprocess.run(["ruff", "check", "src"])
    
    # Run Black (formatting check)
    print("\n--- Running Black ---")
    black_res = subprocess.run(["black", "--check", "src"])

    if ruff_res.returncode == 0 and black_res.returncode == 0:
        print("\n✅ All checks passed!")
        sys.exit(0)
    else:
        print("\n❌ Some checks failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
