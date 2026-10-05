#!/bin/bash

# 🔄 vLooper Harness: Combined Quality Check & Test Suite
# This script is used by the vLooper daemon to verify code changes.

# Helper function to run a command and strip output on failure
run_and_strip() {
    local label="$1"
    local cmd="$2"
    local error_msg="$3"
    local output
    
    echo "$label"
    
    # Capture both stdout and stderr
    output=$(eval "$cmd" 2>&1)
    local status=$?
    
    if [ $status -ne 0 ]; then
        echo "❌ $error_msg"
        echo "--- Last 50 lines of output ---"
        # Use printf to handle the potentially large output safely
        printf "%s\n" "$output" | tail -n 50
        return $status
    fi

    # If successful, print the captured output if it's not empty
    if [ -n "$output" ]; then
        printf "%s\n" "$output"
    fi
    return 0
}

echo "🚀 Starting full quality check..."

# 1. Run linting, type checking, and formatting checks
run_and_strip "🔍 Step 1: Running code quality checks (uv run check)..." "uv run check" "Code quality checks failed! Please fix the issues above." || exit 1

# 2. Run the unit test suite
run_and_strip "🧪 Step 2: Running test suite (uv run pytest)..." "uv run pytest" "Unit tests failed! Please fix the logic errors." || exit 1

echo "🎉 All checks passed! Code is clean and functional."
exit 0
