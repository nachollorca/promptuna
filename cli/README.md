# promptuna-cli

> CLI surface for the [`promptuna`](https://pypi.org/project/promptuna/) evaluation harness. See the [main project README](https://github.com/nachollorca/promptuna#readme) for the full overview, library API, and usage surfaces.

Typer CLI for on-disk promptuna projects. Installed as a separate package (pulls in `promptuna`):

```bash
pip install promptuna-cli
```

## Commands

```bash
promptuna run -p <project> --program <name> --prompt <name> --examples <name> -m <model>
promptuna evaluate ... -M <metric> [-M <metric> ...]
promptuna optimize ... -M <metric> --steps <n> --proposer-model <model>
promptuna report <job_id>
```

Global option `--projects-root` overrides `PROMPTUNA_PROJECTS_ROOT` (default: repo `samples/` in a dev checkout).

Output defaults to markdown on stdout for `run`, `evaluate`, and `optimize`. Use `--format json` for the job `summary.json`. `report` always prints `summary.json`. Each finished job prints `job_id` on stderr and writes artifacts under `<projects_root>/jobs/<job_id>/`.

`--metric` accepts repeated flags and comma-separated lists (`-M a,b`).
