#!/bin/bash

# 🔄 vLooper Harness: Combined Quality Check & Test Suite
# This script is used by the vLooper daemon to verify code changes.

echo "🚀 Starting full quality check..."

# Helper function to run a command and handle output stripping on failure
run_with_stripping() {
    local step_name="$1"
    local cmd="$2"
    local error_msg="$3"
    local log_file
    log_file=$(mktemp)

    echo "$step_name"
    if ! eval "$cmd" > "$log_file" 2>&1; then
        echo "❌ $error_msg"
        tail -n 50 "$log_file"
        rm "$log_file"
        return 1
    fi
    cat "$log_file"
    rm "$log_file"
    return 0
}

# 1. Run linting, type checking, and formatting checks
run_with_stripping \
    "🔍 Step 1: Running code quality checks (uv run check)..." \
    "uv run check" \
    "Code quality checks failed! Please fix the issues above." || exit 1

# 2. Run the unit test suite
run_with_stripping \
    "🧪 Step 2: Running test suite (uv run pytest)..." \
    "uv run pytest" \
    "Unit tests failed! Please fix the logic errors." || exit 1

echo "🎉 All checks passed! Code is clean and functional."
exit 0
