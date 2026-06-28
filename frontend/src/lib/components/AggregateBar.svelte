<script lang="ts">
	import type { EventStoreState } from '$lib/types';
	import { computeOverallMean, perMetricMeans } from '$lib/eventStore';

	interface Props {
		store: EventStoreState;
		complete: boolean;
	}

	let { store, complete }: Props = $props();

	const agg = $derived(store.aggregates);
	const metrics = $derived(perMetricMeans(agg));
	const overall = $derived(computeOverallMean(agg));
</script>

{#if agg.trialTotal > 0}
	<div class="aggregate-bar">
		<span
			><strong>{agg.trialSuccess}/{agg.trialTotal}</strong> trials succeeded{#if !complete}
				<span class="partial"> (partial)</span>{/if}</span
		>
		{#if agg.scoringTotal > 0}
			<span
				><strong>{agg.scoringSuccess}/{agg.scoringTotal}</strong> scorings{#if !complete}
					<span class="partial"> (partial)</span>{/if}</span
			>
		{/if}
		{#each Object.entries(metrics) as [name, stats] (name)}
			<span
				>{name} <strong>{stats.mean.toFixed(2)}</strong>{#if !complete}
					<span class="partial"> (partial)</span>{/if}</span
			>
		{/each}
		{#if overall !== null && Object.keys(metrics).length > 1}
			<span
				>overall <strong>{overall.toFixed(2)}</strong>{#if !complete}
					<span class="partial"> (partial)</span>{/if}</span
			>
		{/if}
		{#if agg.inputTokens > 0}
			<span
				>tokens <strong>{agg.inputTokens}</strong> in / <strong>{agg.outputTokens}</strong> out</span
			>
		{/if}
	</div>
{/if}

<style>
	.partial {
		font-style: italic;
	}
</style>
