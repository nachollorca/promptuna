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
format *paths=".":
    uv run --frozen ruff check --fix {{ paths }}
    uv run --frozen ruff format {{ paths }}

check-types *paths=".":
    uv run --frozen ty check {{ paths }}

check-complexity *paths=".":
    uv run --frozen complexipy {{ paths }}

# Test and run ----------------------------------------------------------------
test target="":
    uv run --frozen pytest --cov --cov-fail-under=90 {{ target }}

run file:
    uv run --frozen --env-file .env {{ file }}

# Project specific commands ---------------------------------------------------
notebook:
    uv run --frozen jupyter lab

# Uses bundled samples/ by default; set PROMPTUNA_PROJECTS_ROOT to override.
server:
    uv run --frozen uvicorn promptuna_server.main:app --reload --port 6969


# Frontend --------------------------------------------------------------------
frontend-install:
    npm ci --prefix frontend

frontend-format:
    npm run format --prefix frontend
    npm run lint:fix --prefix frontend

frontend-check:
    npm run check --prefix frontend
    npm run lint --prefix frontend
    npm run format:check --prefix frontend

frontend-build:
    npm run build --prefix frontend

frontend-dev:
    npm run dev --prefix frontend

# Container image (packaged UI + API on one port) ---------------------------
# Uses podman when available, otherwise docker. Override: CONTAINER_ENGINE=docker
container-engine := env_var_or_default('CONTAINER_ENGINE', `command -v podman >/dev/null 2>&1 && echo podman || echo docker`)
docker-image := "promptuna:local"

docker-build:
    {{ container-engine }} build -t {{ docker-image }} .

docker-run *args:
    #!/usr/bin/env bash
    set -euo pipefail
    env_args=()
    if [[ -f .env ]]; then env_args=(--env-file .env); fi
    {{ container-engine }} run --rm -p 8080:8080 "${env_args[@]}" {{ args }} {{ docker-image }}
