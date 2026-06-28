<script lang="ts">
	import type { EventStoreState, StepSection as StepSectionType } from '$lib/types';
	import { THINKING_FIELDS } from '$lib/types';
	import TrialRow from './TrialRow.svelte';

	interface Props {
		step: StepSectionType;
		store: EventStoreState;
		previousScore: number | null;
		expandedTrials: Set<string>;
		onToggleTrial: (trialId: string) => void;
	}

	let { step, store, previousScore, expandedTrials, onToggleTrial }: Props = $props();

	let thinkingOpen = $state(false);

	const delta = $derived(
		step.step && previousScore !== null ? step.step.score - previousScore : null
	);
</script>

<section class="step-section panel">
	<header class="step-header">
		<h3>Step {step.stepIndex}</h3>
		{#if step.step}
			<span class="score">Score: <strong>{step.step.score.toFixed(3)}</strong></span>
			{#if delta !== null}
				<span class="delta" class:positive={delta > 0} class:negative={delta < 0}>
					Δ {delta >= 0 ? '+' : ''}{delta.toFixed(3)}
				</span>
			{/if}
		{:else}
			<span class="muted">In progress…</span>
		{/if}
	</header>

	{#if step.proposal}
		<div class="proposal-block">
			<h4>Proposal</h4>
			{#if step.proposal.thinking}
				<button
					type="button"
					class="thinking-toggle"
					onclick={() => (thinkingOpen = !thinkingOpen)}
				>
					{thinkingOpen ? '▼' : '▶'} Proposer thinking
				</button>
				{#if thinkingOpen}
					<div class="thinking-sections">
						{#each THINKING_FIELDS as field (field.key)}
							<div class="thinking-item">
								<span class="thinking-label">{field.label}</span>
								<p>{step.proposal.thinking![field.key]}</p>
							</div>
						{/each}
					</div>
				{/if}
			{:else if step.stepIndex === 0}
				<p class="muted">Baseline step (no proposer thinking)</p>
			{/if}
			<p class="muted">Prompt template</p>
			<pre class="mono">{step.proposal.prompt_template}</pre>
		</div>
	{/if}

	<div class="trials">
		{#each step.trialIds as trialKey (trialKey)}
			{@const entry = store.trialsById.get(trialKey)}
			{#if entry}
				<TrialRow
					trial={entry.trial}
					scorings={entry.scorings}
					expanded={expandedTrials.has(trialKey)}
					onToggle={() => onToggleTrial(trialKey)}
				/>
			{/if}
		{/each}
	</div>

	{#if step.step}
		<footer class="step-footer">
			<span
				>Overall mean: <strong>{step.step.summary.overall.mean.toFixed(3)}</strong> (n={step.step
					.summary.overall.n})</span
			>
			{#each Object.entries(step.step.summary.per_metric) as [name, stats] (name)}
				<span>{name}: {stats.mean.toFixed(3)}</span>
			{/each}
			<span>Failure rate: {(step.step.summary.failure_rate * 100).toFixed(1)}%</span>
		</footer>
	{/if}
</section>

<style>
	.step-section {
		margin-bottom: 1rem;
	}

	.step-header {
		display: flex;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
		margin-bottom: 0.75rem;
	}

	.step-header h3 {
		margin: 0;
		font-size: 1rem;
	}

	.score strong {
		font-size: 1.05rem;
	}

	.delta {
		font-size: 0.875rem;
		padding: 0.1rem 0.45rem;
		border-radius: 4px;
		background: #f0f2f5;
	}

	.delta.positive {
		color: var(--success);
		background: #edf9f1;
	}

	.delta.negative {
		color: var(--danger);
		background: #fdecec;
	}

	.proposal-block {
		margin-bottom: 0.75rem;
		padding-bottom: 0.75rem;
		border-bottom: 1px solid var(--border);
	}

	.proposal-block h4 {
		margin: 0 0 0.5rem;
		font-size: 0.875rem;
		color: var(--muted);
	}

	.thinking-toggle {
		border: none;
		background: none;
		padding: 0;
		color: var(--accent);
		font-size: 0.875rem;
		margin-bottom: 0.5rem;
	}

	.thinking-sections {
		display: grid;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}

	.thinking-item {
		font-size: 0.875rem;
	}

	.thinking-label {
		display: block;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--muted);
		margin-bottom: 0.15rem;
	}

	.thinking-item p {
		margin: 0;
	}

	.step-footer {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem 1rem;
		margin-top: 0.75rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--border);
		font-size: 0.8125rem;
		color: var(--muted);
	}
</style>
