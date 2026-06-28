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
		if (colorMode === 'grey') return 'border-color: var(--border); background: var(--surface-dim)';
		if (colorMode === 'green') return 'border-color: var(--success); background: var(--success-bg)';
		if (worstScore !== null) {
			return `border-color: ${scoreGradient(worstScore).replace('88%', '55%')}; background: ${scoreGradient(worstScore).replace('88%', '92%')}`;
		}
		return '';
	});

	function scoreTier(normalized: number): 'green' | 'amber' | 'red' {
		if (normalized >= 0.66) return 'green';
		if (normalized >= 0.33) return 'amber';
		return 'red';
	}

	const inputsSummary = $derived(snippet(trial.example.inputs, 60));
	const outputSummary = $derived(
		trial.status === 'failed' ? (trial.error?.message ?? 'Failed') : snippet(trial.output, 60)
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
						<span class="chip {scoreTier(scoring.score.normalized)}" title={scoring.score.reason}>
							<span class="chip-metric">{scoring.metric.name}</span>
							<span class="chip-value">{scoring.score.normalized.toFixed(2)}</span>
						</span>
					{:else}
						<span class="chip failed">
							<span class="chip-metric">{scoring.metric.name}</span>
							<span class="chip-value">FAILED</span>
						</span>
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
		margin-bottom: var(--space-sm);
		overflow: hidden;
		transition: border-width 0.05s ease;
	}

	.trial-row.expanded {
		border-width: 2px;
	}

	.trial-header {
		width: 100%;
		display: flex;
		align-items: center;
		gap: var(--space-sm);
		padding: var(--space-sm) var(--space-md);
		border: none;
		background: transparent;
		text-align: left;
	}

	.trial-header:hover {
		background: rgba(15, 23, 42, 0.03);
	}

	.chevron {
		color: var(--muted);
		font-family: var(--font-mono);
		font-size: 10px;
		flex-shrink: 0;
	}

	.trial-summary {
		flex: 1;
		display: flex;
		align-items: center;
		gap: var(--space-sm);
		min-width: 0;
		font-family: var(--font-mono);
		font-size: 13px;
		line-height: 20px;
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
		gap: var(--space-xs);
		flex-shrink: 0;
	}

	.chip {
		display: inline-flex;
		align-items: baseline;
		gap: var(--space-xs);
		padding: 1px var(--space-sm);
		border: 1px solid transparent;
		font-family: var(--font-mono);
		font-size: 11px;
		line-height: 16px;
		letter-spacing: 0.03em;
	}

	.chip-metric {
		font-weight: 500;
		text-transform: uppercase;
		opacity: 0.7;
	}

	.chip-value {
		font-weight: 600;
	}

	/* Functional scoring colors: 10% bg + full-color text + border */
	.chip.green {
		background: var(--success-bg);
		border-color: var(--success);
		color: var(--success);
	}

	.chip.amber {
		background: var(--warning-bg);
		border-color: var(--warning);
		color: var(--warning);
	}

	.chip.red,
	.chip.failed {
		background: var(--danger-bg);
		border-color: var(--danger);
		color: var(--danger);
	}

	.trial-detail {
		padding: 0 var(--space-md) var(--space-md);
		border-top: 1px solid var(--border);
	}

	.trial-detail section {
		margin-top: var(--space-md);
	}

	.trial-detail h4 {
		margin: 0 0 var(--space-sm);
		font-family: var(--font-mono);
		font-size: 11px;
		font-weight: 500;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--muted);
	}

	.trial-detail pre.mono {
		margin: 0;
		padding: var(--space-md);
		background: var(--surface-secondary);
		border: 1px solid var(--border);
	}

	.telemetry-stats {
		margin: var(--space-xs) 0 0;
		padding: var(--space-sm) var(--space-md) var(--space-sm) var(--space-lg);
		font-family: var(--font-mono);
		font-size: 13px;
		line-height: 22px;
		border: 1px solid var(--border);
		background: var(--surface-secondary);
		list-style: square;
	}

	.error-text {
		color: var(--danger);
		margin: 0;
		font-family: var(--font-mono);
		font-size: 13px;
	}
</style>
