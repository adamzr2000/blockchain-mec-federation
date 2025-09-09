#!/usr/bin/env bash
# remove_csvs.sh - Delete all CSV files in a given experiment directory

set -euo pipefail

# Default directory is "test", but allow override via first argument
TARGET_DIR="${1:-test}"

# Ensure we're in the correct experiments folder
BASE_DIR="$(pwd)"

# Full path to target dir
FULL_PATH="$BASE_DIR/$TARGET_DIR"

if [[ ! -d "$FULL_PATH" ]]; then
    echo "❌ Directory '$FULL_PATH' does not exist."
    exit 1
fi

echo "🧹 Removing CSV files under: $FULL_PATH"

# Find and delete all .csv files under target dir
find "$FULL_PATH" -type f -name "*.csv" -exec rm -f {} +

echo "✅ Done."
