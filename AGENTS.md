# AGENTS.md

## Cursor Cloud specific instructions

`promptuna` is a single Python library (a Language Model Evaluation Harness), not a
multi-service app — there is no server, frontend, or database. Tooling: Python (uv
auto-installs an interpreter satisfying `requires-python = ">=3.13"`), `uv` for
dependency management, and `just` as the task runner. Canonical commands live in
the `justfile`; CI is `.github/workflows/verify.yml`.

- Dependencies are pre-installed by the startup update script (`just install` →
  `uv sync --frozen --all-extras --all-groups`). `uv`/`just` live in `~/.local/bin`
  (on PATH via `~/.profile`/`~/.bashrc`).
- Common commands (see `justfile`): `just test` (pytest with a ≥90% coverage gate),
  `just format` (ruff), `just check-types` (ty), `just check-complexity` (complexipy),
  `just notebook` (JupyterLab for `getting_started.ipynb`).
- The test suite is fully self-contained: `tests/conftest.py`/`tests/helpers.py` patch
  `lmdk.complete`, so **no API keys or network access are needed** to run tests.
- Running real LM evaluations (`getting_started.py`, `just run <file>`) IS live and
  needs secrets: `LOGFIRE_TOKEN` plus LM provider credentials (Mistral, Google Vertex).
  These are loaded from a `.env` file (`set dotenv-load` in the `justfile`; no `.env`
  is committed). Skip these unless those secrets are configured.
- To exercise the library without live keys, patch `lmdk.complete` to record on the
  active observer via `lmdk.observe._current_observer()._record(request, response)` —
  `run_trial` asserts `complete` is called exactly once per trial, so a fake that does
  not record will produce a `FailedTrial`.
