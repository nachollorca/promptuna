# Sample projects

Bundled reference projects for development and documentation. Each subdirectory is a **project** the project loader can resolve by name.

This is not where end-user projects live in production — a future `promptuna init` will scaffold a workspace elsewhere. These samples ship with the repo so contributors have a working example to copy.

## Layout

```
samples/<project_name>/
├── programs.py       # callables adhering to the Program protocol (or program.py)
├── metrics.py        # ProgrammaticMetric / LLMJudgeMetric instances
├── prompt.jinja      # single-prompt projects (prompt name: "prompt")
├── prompts/          # multi-prompt projects (instead of prompt.jinja)
│   └── <name>.jinja  # Jinja2 templates (placeholders match program kwargs)
└── data/
    └── <name>.jsonl  # dataset rows (inputs + optional reference)
```

Use either the root `prompt.jinja` or a `prompts/` directory. When `prompts/`
contains any `.jinja` file it wins and `prompt.jinja` is ignored.

### `programs.py` / `program.py`

Each program is a Python function that:

- accepts `prompt_template`, `model`, and `**inputs` (from dataset rows)
- may optionally accept `generation_kwargs`
- calls `lmdk.complete` exactly once inside a deterministic scaffold

Names are the function names (e.g. `v1`).

### `metrics.py`

Each metric is a module-level instance of `ProgrammaticMetric` or `LLMJudgeMetric`. Names are the variable names (e.g. `label_correctness`).

### `prompt.jinja` / `prompts/*.jinja`

Plain Jinja2 templates. Placeholder names must match what the program passes to `render_template` (e.g. `{{ REVIEW }}`). A single-prompt project keeps `prompt.jinja` at the project root and uses the prompt name `prompt`; multi-prompt projects put `<name>.jinja` files in `prompts/`.

### `data/*.jsonl`

One JSON object per line with an `inputs` dict and an optional `reference`. Loaded via `promptuna.load.load_jsonl` into `Example` rows.

## Projects root

The loader discovers projects as subdirectories of a **projects root**. Resolution order (highest priority first):

1. **`set_projects_root()`** — programmatic override (typically in tests)
2. **`PROMPTUNA_PROJECTS_ROOT`** — environment variable pointing at a directory
3. **Default** — repo `samples/` in a development checkout

Each immediate subdirectory of the projects root is one project (e.g. `classify_sentiment/`).
