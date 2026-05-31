# Language Model Evaluation Harness

`lmeh` evaluates *functions that use an LM* to accomplish a goal, not bare completion calls.

Such function can optionally surrounded by arbitrary deterministic code that prepares the prompt (pre-processing) and refines the model's output (post-processing).

See the [getting started notebook](cookbook/getting_started.ipynb) for a full walkthrough.

Inspired by DSPy, Ragas, OPRO.

## License
MIT

_Made with [mold](https://github.com/nachollorca/mold)_
