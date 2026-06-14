# Promptuna

`promptuna` evaluates and optimizes *functions that use an LM* to accomplish a goal.

Such functions (hereinafter referred to as **programs**) do not contain just the bare completion call: they can be surrounded by arbitrary code that prepares the prompt (pre-processing) and refines the model's output (post-processing) - as it is typically the case in real-world scenarios (you don't just "call a model" and return the raw output).

In the refinement loop below, `promptuna` provides the primitives for you to define the metrics that judge how well your program performs (3). Then, it can use those scores to drive automated improvements on the prompt template (4).

```mermaid
flowchart LR
    A[1. Make a program] --> B[2. Run the program]
    B --> C[3. Evaluate the program]
    C --> D[4. Improve the program]
    D --> B
```

The loop above maps directly onto the package layout:

| Step | Module | Role | Key API |
| --- | --- | --- | --- |
| 1. Make a program | [`promptuna.program`](src/promptuna/program.py) | Wire what is under test | `Program`, `Example`, `Experiment`, `LMConfig` |
| 2. Run the program | [`promptuna.run`](src/promptuna/run.py) | Execute a program on one dataset row | `run_trial`, `Trial` |
| 3. Evaluate the program | [`promptuna.evaluate`](src/promptuna/evaluate.py) | Score trials and run full experiments | `Metric`, `run_experiment`, `RunResults`, `default_llm_judge` |
| 4. Improve the program | [`promptuna.optimize`](src/promptuna/optimize.py) | Search for a better prompt template | `optimize`, `Step`, `OptimizationResult` |

[`promptuna.report`](src/promptuna/report.py) sits alongside evaluation and optimization: it renders `RunResults` and optimization trajectories as markdown (`render_run`, `render_history`).

**See the [getting started notebook](getting_started.ipynb) for a full working example of this cycle end to end.**

## Optimization

Prompt-template search (OPRO-style) treats evaluation as **multi-criteria**: each candidate is scored on several normalized metrics, forming a quality vector in metric space. Before comparing checkpoints, that vector is collapsed by a fixed **linear scalarization**—the unweighted mean of per-metric means (`RunResults.overall.mean`), a compensatory aggregation where gains on one metric can offset losses on another. The search is therefore **single-objective** in template space: it maximizes one scalar utility, keeps the best checkpoint seen so far, and does not explore a Pareto front over metrics. The proposer still receives per-metric breakdowns in the trajectory (`render_history`); only ranking and early stopping use the headline score.

## Inspiration

`promptuna` is a proud Frankenstein of [DSPy](https://github.com/stanfordnlp/dspy), [Ragas](https://github.com/vibrantlabsai/ragas), [OPRO](https://arxiv.org/pdf/2309.03409)] and [Optuna](https://github.com/optuna/optuna).

First and foremost, `promptuna`'s value proposition is most similar to [DSPy](https://github.com/stanfordnlp/dspy). The differences:
- **Programs:** DSPy models a program as a composable graph of predictors (`dspy.Module`). `promptuna` treats a program as an ordinary Python function: arbitrary pre/post-processing around a completion call, without forcing signature/module abstractions.
- **Evaluation.** DSPy passes a single metric callable to its optimizers. Multiple quality dimensions must be folded into that one function by hand. `promptuna` takes a `list[Metric]` instead: each metric has its own name, scale (`Range`, `Ordinal`, …), and scorer (programmatic or LLM judge). Results are naively aggregated to collapse multiple metrics into the single optimization objective.
- **Optimization.** DSPy offers several teleprompters. `promptuna`'s simple optimizer is OPRO-style: it rewrites a free-form prompt template from a trajectory, using the same multi-metric evaluation harness at every step, keeping the full metric breakdown visible throughout the search.

Some ideas regarding evaluation metrics are taken from the seemingly already abandoned [ragas](https://github.com/vibrantlabsai/ragas): named metrics where an LLM judge scores a trial against a rubric, with typed scales and optional rationales.

The optimization loop itself takes concepts from [DeepMind's OPRO](https://arxiv.org/pdf/2309.03409): at each step an LM proposer rewrites the prompt template from scratch using the full scored history of prior candidates.

The name of the package itself is a reference to the infamous [Optuna](https://github.com/optuna/optuna): a fixed-budget search over trials that archives every checkpoint and returns the best one seen.

## License
MIT

_Made with [mold](https://github.com/nachollorca/mold)_
