#!/bin/bash

# 🔄 vLooper Harness: Combined Quality Check & Test Suite
# This script is used by the vLooper daemon to verify code changes.

echo "🚀 Starting full quality check..."

# 1. Run linting, type checking, and formatting checks
echo "🔍 Step 1: Running code quality checks (uv run check)..."
if ! uv run check; then
    echo "❌ Code quality checks failed!"
    exit 1
fi

# 2. Run the unit test suite
echo "🧪 Step 2: Running test suite (uv run pytest)..."
if ! uv run pytest; then
    echo "❌ Unit tests failed!"
    exit 1
fi

echo "🎉 All checks passed! Code is clean and functional."
exit 0
