<script lang="ts">
	import type { EventStoreState, JobSummary } from '$lib/types';
	import { computeOverallMean, perMetricMeans } from '$lib/eventStore';

	interface Props {
		summary: JobSummary | null;
		store: EventStoreState;
		complete: boolean;
	}

	let { summary, store, complete }: Props = $props();

	const liveMetrics = $derived(perMetricMeans(store.aggregates));
	const liveOverall = $derived(computeOverallMean(store.aggregates));
	const agg = $derived(store.aggregates);
</script>

{#if summary || agg.trialTotal > 0}
	<section class="panel">
		<h2>Summary</h2>
		{#if summary}
			<div class="summary-grid">
				<div>
					<span class="label">Trials</span>
					<strong>{summary.trial_count}</strong>
					<span class="muted"> · failure rate {(summary.failure_rate * 100).toFixed(1)}%</span>
				</div>
				{#if summary.scoring_count > 0}
					<div>
						<span class="label">Scorings</span>
						<strong>{summary.scoring_count}</strong>
						<span class="muted">
							· scoring failure {(summary.scoring_failure_rate * 100).toFixed(1)}%
						</span>
					</div>
				{/if}
				{#if summary.overall}
					<div>
						<span class="label">Overall mean</span>
						<strong>{summary.overall.mean.toFixed(3)}</strong>
						<span class="muted"> (n={summary.overall.n})</span>
					</div>
				{/if}
				{#each Object.entries(summary.per_metric) as [name, stats] (name)}
					<div>
						<span class="label">{name}</span>
						<strong>{stats.mean.toFixed(3)}</strong>
						<span class="muted"> (n={stats.n})</span>
					</div>
				{/each}
				<div>
					<span class="label">Tokens</span>
					<strong>{summary.telemetry.input_tokens}</strong> in /
					<strong>{summary.telemetry.output_tokens}</strong> out
				</div>
				<div>
					<span class="label">Latency</span>
					<strong>{summary.telemetry.latency.toFixed(2)}</strong>s total
				</div>
			</div>
			{#if summary.best_step}
				<div class="best-step">
					<strong>Best step:</strong>
					{summary.best_step.step_index} — score
					{summary.best_step.score.toFixed(3)}
				</div>
			{/if}
		{:else}
			<div class="summary-grid">
				<div>
					<span class="label">Trials</span>
					<strong>{agg.trialSuccess}/{agg.trialTotal}</strong> success
					{#if !complete}<span class="partial">(partial)</span>{/if}
				</div>
				{#if agg.scoringTotal > 0}
					<div>
						<span class="label">Scorings</span>
						<strong>{agg.scoringSuccess}/{agg.scoringTotal}</strong>
						{#if !complete}<span class="partial">(partial)</span>{/if}
					</div>
				{/if}
				{#if liveOverall !== null}
					<div>
						<span class="label">Overall mean</span>
						<strong>{liveOverall.toFixed(3)}</strong>
						{#if !complete}<span class="partial">(partial)</span>{/if}
					</div>
				{/if}
				{#each Object.entries(liveMetrics) as [name, stats] (name)}
					<div>
						<span class="label">{name}</span>
						<strong>{stats.mean.toFixed(3)}</strong>
						<span class="muted"> (n={stats.n})</span>
						{#if !complete}<span class="partial">(partial)</span>{/if}
					</div>
				{/each}
				<div>
					<span class="label">Tokens</span>
					<strong>{agg.inputTokens}</strong> in / <strong>{agg.outputTokens}</strong> out
				</div>
				<div>
					<span class="label">Latency</span>
					<strong>{agg.latency.toFixed(2)}</strong>s
				</div>
			</div>
		{/if}
	</section>
{/if}

<style>
	.summary-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 0.65rem 1rem;
		font-size: 0.875rem;
	}

	.label {
		display: block;
		font-size: 0.75rem;
		color: var(--muted);
		margin-bottom: 0.1rem;
	}

	.partial {
		color: var(--muted);
		font-size: 0.8125rem;
		margin-left: 0.25rem;
	}

	.best-step {
		margin-top: 0.75rem;
		padding: 0.6rem 0.75rem;
		background: #edf9f1;
		border-radius: 6px;
		font-size: 0.875rem;
	}
</style>
