<script lang="ts">
	import type { TrialPayload, ScoringPayload } from '$lib/types';
	import {
		formatValue,
		scoreGradient,
		snippet,
		trialRowColor,
		worstNormalizedScore
	} from '$lib/eventStore';

	interface Props {
		trial: TrialPayload;
		scorings: ScoringPayload[];
		expanded: boolean;
		onToggle: () => void;
	}

	let { trial, scorings, expanded, onToggle }: Props = $props();

	const colorMode = $derived(trialRowColor(trial, scorings));
	const worstScore = $derived(worstNormalizedScore(scorings));

	const borderStyle = $derived.by(() => {
		if (colorMode === 'grey') return 'border-color: #b8bec8; background: #f3f4f6';
		if (colorMode === 'green') return 'border-color: #6bc98a; background: #edf9f1';
		if (worstScore !== null) {
			return `border-color: ${scoreGradient(worstScore).replace('88%', '65%')}; background: ${scoreGradient(worstScore)}`;
		}
		return '';
	});

	const inputsSummary = $derived(snippet(trial.example.inputs, 60));
	const outputSummary = $derived(
		trial.status === 'failed'
			? trial.error?.message ?? 'Failed'
			: snippet(trial.output, 60)
	);
</script>

<article class="trial-row" class:expanded style={borderStyle}>
	<button type="button" class="trial-header" onclick={onToggle} aria-expanded={expanded}>
		<span class="chevron">{expanded ? '▼' : '▶'}</span>
		<span class="trial-summary">
			<span class="inputs">{inputsSummary}</span>
			<span class="arrow">→</span>
			<span class="output" class:failed={trial.status === 'failed'}>{outputSummary}</span>
		</span>
		{#if scorings.length > 0}
			<span class="score-chips">
				{#each scorings as scoring (scoring.metric.name + scoring.replicate)}
					{#if scoring.status === 'success' && scoring.score}
						<span class="chip" title={scoring.score.reason}>
							{scoring.metric.name}: {scoring.score.normalized.toFixed(2)}
						</span>
					{:else}
						<span class="chip failed">{scoring.metric.name}: failed</span>
					{/if}
				{/each}
			</span>
		{/if}
	</button>

	{#if expanded}
		<div class="trial-detail">
			<section>
				<h4>Inputs</h4>
				<pre class="mono">{formatValue(trial.example.inputs)}</pre>
			</section>
			<section>
				<h4>Reference</h4>
				<pre class="mono">{formatValue(trial.example.reference)}</pre>
			</section>
			{#if trial.status === 'success'}
				<section>
					<h4>Output</h4>
					<pre class="mono">{formatValue(trial.output)}</pre>
				</section>
				{#if trial.telemetry}
					<section>
						<h4>Telemetry</h4>
						{#if trial.telemetry.rendered_prompt}
							<p class="muted">Rendered prompt</p>
							<pre class="mono">{trial.telemetry.rendered_prompt}</pre>
						{/if}
						{#if trial.telemetry.response}
							<ul class="telemetry-stats">
								<li>Tokens in: {trial.telemetry.response.input_tokens ?? '—'}</li>
								<li>Tokens out: {trial.telemetry.response.output_tokens ?? '—'}</li>
								<li>Latency: {trial.telemetry.response.latency?.toFixed(3) ?? '—'}s</li>
							</ul>
						{/if}
					</section>
				{/if}
			{:else if trial.error}
				<section>
					<h4>Error</h4>
					<p class="error-text">{trial.error.type}: {trial.error.message}</p>
				</section>
			{/if}
			{#each scorings as scoring (scoring.metric.name + scoring.replicate)}
				<section>
					<h4>Scoring — {scoring.metric.name}</h4>
					{#if scoring.status === 'success' && scoring.score}
						<p>Normalized: <strong>{scoring.score.normalized.toFixed(3)}</strong></p>
						<p class="muted">Reason</p>
						<pre class="mono">{scoring.score.reason}</pre>
					{:else if scoring.error}
						<p class="error-text">{scoring.error.type}: {scoring.error.message}</p>
					{/if}
				</section>
			{/each}
		</div>
	{/if}
</article>

<style>
	.trial-row {
		border: 1px solid var(--border);
		border-radius: var(--radius);
		margin-bottom: 0.5rem;
		overflow: hidden;
	}

	.trial-header {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.6rem 0.75rem;
		border: none;
		background: transparent;
		text-align: left;
	}

	.trial-header:hover {
		background: rgba(0, 0, 0, 0.02);
	}

	.chevron {
		color: var(--muted);
		font-size: 0.7rem;
		flex-shrink: 0;
	}

	.trial-summary {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 0.35rem;
		min-width: 0;
		font-size: 0.875rem;
	}

	.inputs,
	.output {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.arrow {
		color: var(--muted);
		flex-shrink: 0;
	}

	.output.failed {
		color: var(--danger);
	}

	.score-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		flex-shrink: 0;
	}

	.chip {
		font-size: 0.75rem;
		padding: 0.1rem 0.45rem;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.7);
		border: 1px solid rgba(0, 0, 0, 0.08);
	}

	.chip.failed {
		color: var(--danger);
	}

	.trial-detail {
		padding: 0 0.75rem 0.75rem;
		border-top: 1px solid rgba(0, 0, 0, 0.06);
	}

	.trial-detail section {
		margin-top: 0.75rem;
	}

	.trial-detail h4 {
		margin: 0 0 0.35rem;
		font-size: 0.8125rem;
		color: var(--muted);
		font-weight: 600;
	}

	.telemetry-stats {
		margin: 0.25rem 0 0;
		padding-left: 1.1rem;
		font-size: 0.875rem;
	}

	.error-text {
		color: var(--danger);
		margin: 0;
		font-size: 0.875rem;
	}
</style>
