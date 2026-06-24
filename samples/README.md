# Sample projects

Bundled reference projects for development and documentation. Each subdirectory is a **project** the workspace loader can resolve by name.

This is not where end-user projects live in production — a future `promptuna init` will scaffold a workspace elsewhere. These samples ship with the repo so contributors have a working example to copy.

## Layout

```
samples/<project_name>/
├── programs.py       # callables adhering to the Program protocol
├── metrics.py        # ProgrammaticMetric / LLMJudgeMetric instances
├── prompts/
│   └── <name>.jinja  # Jinja2 templates (placeholders match program kwargs)
└── data/
    └── <name>.jsonl  # dataset rows (inputs + optional reference)
```

### `programs.py`

Each program is a Python function that:

- accepts `prompt_template`, `model`, and `**inputs` (from dataset rows)
- may optionally accept `generation_kwargs`
- calls `lmdk.complete` exactly once inside a deterministic scaffold

Names are the function names (e.g. `v1`).

### `metrics.py`

Each metric is a module-level instance of `ProgrammaticMetric` or `LLMJudgeMetric`. Names are the variable names (e.g. `label_correctness`).

### `prompts/*.jinja`

Plain Jinja2 templates. Placeholder names must match what the program passes to `render_template` (e.g. `{{ REVIEW }}`).

### `data/*.jsonl`

One JSON object per line with an `inputs` dict and an optional `reference`. Loaded via `promptuna.load.load_jsonl` into `Example` rows.
