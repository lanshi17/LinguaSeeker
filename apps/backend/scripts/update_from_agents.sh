#!/bin/bash

# Script to update current branch from yangzs-agents while preserving the literature directory
# This script is designed for the backend literature acquisition worktree branch

set -e  # Exit immediately if a command exits with a non-zero status

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Starting update from yangzs-agents branch..."
echo "Repository root: $REPO_ROOT"
cd "$REPO_ROOT"

# Check if we're in the right directory
if [ ! -d ".git" ]; then
    echo "Error: Not in a git repository root"
    exit 1
fi

# Store current branch name
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"

# Fetch the latest yangzs-agents branch
echo "Fetching latest yangzs-agents branch..."
git fetch origin yangzs-agents
if [ $? -ne 0 ]; then
    echo "Error: Failed to fetch yangzs-agents branch"
    exit 1
fi

# Backup the literature directory
LITERATURE_DIR="src/domain/literature"
BACKUP_DIR="/tmp/literature_backup_$(date +%s)"

echo "Backing up literature directory to $BACKUP_DIR..."
if [ -d "$LITERATURE_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
    cp -r "$LITERATURE_DIR"/* "$BACKUP_DIR"/ 2>/dev/null || echo "Literature directory may be empty"
else
    echo "Literature directory does not exist, creating backup dir anyway"
    mkdir -p "$BACKUP_DIR"
fi

# Reset to yangzs-agents state
echo "Resetting to yangzs-agents branch state..."
git reset --hard origin/yangzs-agents

if [ $? -ne 0 ]; then
    echo "Error: Failed to reset to yangzs-agents branch"
    # Restore literature directory even on failure
    if [ -d "$BACKUP_DIR" ] && [ "$(ls -A $BACKUP_DIR)" ]; then
        mkdir -p "$LITERATURE_DIR"
        cp -r "$BACKUP_DIR"/* "$LITERATURE_DIR"/ 2>/dev/null || true
    fi
    exit 1
fi

# Restore the literature directory
echo "Restoring literature directory..."
if [ -d "$BACKUP_DIR" ] && [ "$(ls -A $BACKUP_DIR)" ]; then
    mkdir -p "$LITERATURE_DIR"
    cp -r "$BACKUP_DIR"/* "$LITERATURE_DIR"/ 2>/dev/null || true
elif [ ! -d "$LITERATURE_DIR" ]; then
    # If backup was empty and directory doesn't exist, create it
    mkdir -p "$LITERATURE_DIR"
fi

# Clean up backup
rm -rf "$BACKUP_DIR"

echo "Successfully updated from yangzs-agents while preserving literature directory."
echo "Current status:"
git status

echo ""
echo "Update complete!"
echo "Note: You may need to commit any changes to preserve the updated state."
