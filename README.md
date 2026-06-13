# Language Model Evaluation Harness

`lmeh` evaluates and optimizes *functions that use an LM* to accomplish a goal.

> Such functions or programs do not refer only to the bare completion call, but they can be surrounded by arbitrary deterministic code that prepares the prompt (pre-processing) and refines the model's output (post-processing).

In the refinement loop below, `lmeh` provides the primitives for you to define the metrics that judge how well your program performs (3). Then, it can use those scores to drive automated improvements on the prompt template (4).

```mermaid
flowchart LR
    A[1. Make a program] --> B[2. Run the program]
    B --> C[3. Evaluate the program]
    C --> D[4. Improve the program]
    D --> B
```

See the [getting started notebook](cookbook/getting_started.ipynb) for a full working example of this cycle end to end.

## Optimization

Prompt-template search (OPRO-style) treats evaluation as **multi-criteria**: each candidate is scored on several normalized metrics, forming a quality vector in metric space. Before comparing checkpoints, that vector is collapsed by a fixed **linear scalarization**—the unweighted mean of per-metric means (`RunResults.overall.mean`), a compensatory aggregation where gains on one metric can offset losses on another. The search is therefore **single-objective** in template space: it maximizes one scalar utility, keeps the best checkpoint seen so far, and does not explore a Pareto front over metrics. The proposer still receives per-metric breakdowns in the trajectory; only ranking and early stopping use the headline score.

Inspired by DSPy, Ragas, OPRO.

## License
MIT

_Made with [mold](https://github.com/nachollorca/mold)_
