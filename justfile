set dotenv-load

# Python environment ----------------------------------------------------------

# Refresh the lockfile and sync (use when you intentionally want newer deps).
upgrade:
    uv lock --upgrade
    uv sync --all-extras --all-groups

# Install from the committed lockfile (matches CI).
install:
    uv sync --frozen --all-extras --all-groups

# Nuke the venv and reinstall from the lockfile (last-resort env reset).
reset-env:
    rm -rf .venv
    uv sync --frozen --all-extras --all-groups

# Pre-commit hooks ------------------------------------------------------------
install-hooks:
    prek install

update-hooks:
    prek auto-update

run-hooks:
    prek run --show-diff-on-failure --color=always -a

# Code quality ----------------------------------------------------------------
# Paths default to src for manual use; prek passes staged or all matched files.
format *paths:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "{{paths}}" ]; then
        set -- {{paths}}
    else
        set -- src
    fi
    uv run ruff check --fix "$@"
    uv run ruff format "$@"

check-types *paths:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "{{paths}}" ]; then
        set -- {{paths}}
    else
        set -- src
    fi
    uv run ty check "$@"

check-complexity *paths:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "{{paths}}" ]; then
        set -- {{paths}}
    else
        set -- src
    fi
    uv run complexipy "$@"

# Test and run ----------------------------------------------------------------
test target="":
    uv run pytest --cov --cov-fail-under=90 {{ target }}

run file:
    uv run --env-file .env {{ file }}

# Project specific commands ---------------------------------------------------
notebook:
    uv run jupyter lab
