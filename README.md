# Language Model Evaluation Harness

`lmeh` evaluates *functions that use an LM* to accomplish a goal, not bare completion calls.

Such function can optionally surrounded by arbitrary deterministic code that prepares the prompt (pre-processing) and refines the model's output (post-processing).

See the [getting started notebook](cookbook/getting_started.ipynb) for a full walkthrough.

## Optimization

Prompt-template search (OPRO-style) treats evaluation as **multi-criteria**: each candidate is scored on several normalized metrics, forming a quality vector in metric space. Before comparing checkpoints, that vector is collapsed by a fixed **linear scalarization**—the unweighted mean of per-metric means (`RunResults.overall.mean`), a compensatory aggregation where gains on one metric can offset losses on another. The search is therefore **single-objective** in template space: it maximizes one scalar utility, keeps the best checkpoint seen so far, and does not explore a Pareto front over metrics. The proposer still receives per-metric breakdowns in the trajectory; only ranking and early stopping use the headline score.

Inspired by DSPy, Ragas, OPRO.

## License
MIT

_Made with [mold](https://github.com/nachollorca/mold)_
