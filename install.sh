#!/bin/bash
# Install skill-facets framework into any project
# Usage: bash /path/to/skill-facets/install.sh [--example bioinformatics|web-development]
#
# This creates a .claude/ directory in the current project with:
# - Framework scripts (manifest, router, validator, compiler, etc.)
# - Empty skills.yaml template (or domain example if --example specified)
# - Runtime profile, bootstrap, and hook configuration

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="${PWD}"
CLAUDE_DIR="${TARGET_DIR}/.claude"
EXAMPLE=""

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --example) EXAMPLE="$2"; shift 2 ;;
        --target) TARGET_DIR="$2"; CLAUDE_DIR="${TARGET_DIR}/.claude"; shift 2 ;;
        -h|--help)
            echo "Usage: bash install.sh [--example bioinformatics|web-development] [--target DIR]"
            echo ""
            echo "Installs skill-facets framework into current directory (or --target)."
            echo "Use --example to include domain-specific skills."
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "Installing skill-facets into: ${CLAUDE_DIR}"

# Create directory structure
mkdir -p "${CLAUDE_DIR}/scripts/constraint_validator/checkers"
mkdir -p "${CLAUDE_DIR}/hooks"
mkdir -p "${CLAUDE_DIR}/commands"
mkdir -p "${CLAUDE_DIR}/logs"

# Copy framework code
echo "  Copying framework..."
cp "${SCRIPT_DIR}/framework/"*.py "${CLAUDE_DIR}/scripts/" 2>/dev/null || true
cp -r "${SCRIPT_DIR}/framework/constraint_validator/"* "${CLAUDE_DIR}/scripts/constraint_validator/"
cp "${SCRIPT_DIR}/framework/router/skill_router.py" "${CLAUDE_DIR}/hooks/"

# Copy templates
echo "  Copying templates..."
if [ -z "$EXAMPLE" ]; then
    cp "${SCRIPT_DIR}/templates/skills.yaml.template" "${CLAUDE_DIR}/skills.yaml"
    cp "${SCRIPT_DIR}/templates/runtime_profile.yaml.template" "${CLAUDE_DIR}/runtime_profile.yaml"
else
    echo "  Applying example: ${EXAMPLE}"
    EXAMPLE_DIR="${SCRIPT_DIR}/examples/${EXAMPLE}"
    if [ ! -d "$EXAMPLE_DIR" ]; then
        echo "Error: example '${EXAMPLE}' not found in ${SCRIPT_DIR}/examples/"
        exit 1
    fi
    # Copy example skills.yaml
    if [ -f "${EXAMPLE_DIR}/skills.yaml" ]; then
        cp "${EXAMPLE_DIR}/skills.yaml" "${CLAUDE_DIR}/skills.yaml"
    fi
    # Copy example commands
    if [ -d "${EXAMPLE_DIR}/commands" ]; then
        cp "${EXAMPLE_DIR}/commands/"*.md "${CLAUDE_DIR}/commands/" 2>/dev/null || true
    fi
    # Copy example skills (dual facet)
    if [ -d "${EXAMPLE_DIR}/skills" ]; then
        cp -r "${EXAMPLE_DIR}/skills/"* "${CLAUDE_DIR}/skills/" 2>/dev/null || true
    fi
    # Runtime profile
    cp "${SCRIPT_DIR}/templates/runtime_profile.yaml.template" "${CLAUDE_DIR}/runtime_profile.yaml"
fi

# Copy validate command (always included)
cp "${SCRIPT_DIR}/templates/command.md.template" "${CLAUDE_DIR}/commands/_template.md"

# Copy bootstrap and install scripts
if [ -f "${SCRIPT_DIR}/.claude/bootstrap_env.sh" ]; then
    cp "${SCRIPT_DIR}/.claude/bootstrap_env.sh" "${CLAUDE_DIR}/"
fi
if [ -f "${SCRIPT_DIR}/.claude/install_local.sh" ]; then
    cp "${SCRIPT_DIR}/.claude/install_local.sh" "${CLAUDE_DIR}/"
fi

# Copy requirements
echo "PyYAML" > "${CLAUDE_DIR}/requirements.txt"
echo "Pillow" >> "${CLAUDE_DIR}/requirements.txt"

# Create .gitkeep for logs
touch "${CLAUDE_DIR}/logs/.gitkeep"

echo ""
echo "Done! Next steps:"
echo "  1. cd ${TARGET_DIR}"
echo "  2. bash .claude/bootstrap_env.sh    # Create venv + install deps"
echo "  3. bash .claude/install_local.sh    # Register hook"
echo "  4. Edit .claude/skills.yaml         # Define your skills"
echo ""
if [ -z "$EXAMPLE" ]; then
    echo "Tip: Use --example to start with a pre-built domain:"
    for d in "${SCRIPT_DIR}/examples/"*/; do
        name=$(basename "$d")
        echo "  bash install.sh --example ${name}"
    done
fi
