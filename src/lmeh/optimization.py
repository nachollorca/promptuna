"""Contains the optimization module."""

from dataclasses import dataclass

from lmdk import complete, render_template

from lmeh.datatypes import Example, Experiment, LMConfig, Metric, RunResults
from lmeh.execution import run_experiment


# Maybe we have to double check if Experiment is the right abstraction,
# since we are sweeping over the prompt, which right now is an
# attribute to Experiment
@dataclass(frozen=True)
class Step:
    """The prompt under evaluation and the results it produced."""

    prompt_template: str  # candidate
    result: RunResults


@dataclass
class OptimizationResult:  # this maybe needs a better name
    """The archive of prompts and results produced by the optimizer."""

    steps: list[Step]

    @property
    def best(self) -> Step:
        """The Step that produced the best ``overall.mean``."""
        return NotImplemented

    @property
    def report(self) -> str:  # Probably also not the best name
        """Formats the steps to format them for the optimizer."""
        # We need to find a way to show of the worse examples.
        # Actually this might not be enough, because we need the prompts from previous experiments
        return NotImplemented


default_optimizer_template = """We have a function that uses an LM.
We also have multiple metrics to assess the quality of the LM outputs on a closed dataset.
Now, we are attempting to optimize the prompt to yield better results.

Here are presented the prompts and the resulting benchmark reports.
They are in chronological order, i.e.: the first item is the original prompt
and the results at step 0. The next item is the first candidate produced to improve the results.
Notice that we have a clear mark on the best step so far.

<steps>
{{ STEPS }}
</steps>

Your task is to understand the trajectory and attempt to produce a prompt that
improves the benchmark result.

Feel free to exploit on the best checkpoint or explore pioneer paths.
Output the modified prompt and nothing else.
Whatever you output will
"""
# Maybe we need to have a look at the last line, I am not sure what is the freest way.
# I also guess different optimizer models will bring much different results


def optimize(
    examples: list[Example],
    experiment: Experiment,  # carries the initial prompt
    metrics: list[Metric],  # if > 1, then we are looking for Pareto line / area / volume...
    config: LMConfig,
    steps: int,
    optimizer_template: str = default_optimizer_template,
    workers: int = 1,
) -> OptimizationResult:
    """Iterates X steps on the optimization to produce a better prompt."""
    baseline = run_experiment(
        experiment=experiment, examples=examples, metrics=metrics, workers=workers
    )
    result = OptimizationResult(
        steps=[Step(result=baseline, prompt_template=experiment.prompt_template)]
    )
    i = 0
    optimization_prompt = render_template(template=optimizer_template, STEPS=result.report)
    new_template = complete(
        model=config.model,
        prompt=optimization_prompt,
        generation_kwargs=config.generation_kwargs,
    ).content
    while i < steps:
        experiment.prompt_template = new_template
        experiment_result = run_experiment(
            experiment=experiment, examples=examples, metrics=metrics, workers=workers
        )
        result.steps.append(Step(result=experiment_result, prompt_template=new_template))
        optimization_prompt = render_template(template=optimizer_template, STEPS=result.report)
        new_template = complete(
            model=config.model,
            prompt=optimization_prompt,
            generation_kwargs=config.generation_kwargs,
        ).content
        i += 1
    return NotImplemented


# The variable naming here is shit
# Surely there is also duplication in the function that can be largely improved
