<script lang="ts">
	import type { EventStoreState } from '$lib/types';
	import AggregateBar from './AggregateBar.svelte';
	import StepSection from './StepSection.svelte';
	import TrialRow from './TrialRow.svelte';
	import JobManifest from './JobManifest.svelte';
	import JobSummary from './JobSummary.svelte';

	interface Props {
		store: EventStoreState;
	}

	let { store }: Props = $props();

	let expandedTrials = $state(new Set<string>());

	const complete = $derived(store.status === 'done' || store.status === 'error');
	const kind = $derived(store.manifest?.kind);

	function toggleTrial(trialId: string) {
		const next = new Set(expandedTrials);
		if (next.has(trialId)) {
			next.delete(trialId);
		} else {
			next.add(trialId);
		}
		expandedTrials = next;
	}

	function previousScore(index: number): number | null {
		if (index <= 0) return null;
		const prev = store.steps.find((s) => s.stepIndex === index - 1);
		return prev?.step?.score ?? null;
	}
</script>

{#if store.manifest}
	<JobManifest manifest={store.manifest} />
{/if}

{#if store.errorMessage && store.status === 'error'}
	<div class="error-banner panel">{store.errorMessage}</div>
{/if}

{#if kind === 'optimize'}
	{#each store.steps as step, i (step.stepIndex)}
		<StepSection
			{step}
			{store}
			previousScore={previousScore(step.stepIndex)}
			{expandedTrials}
			onToggleTrial={toggleTrial}
		/>
		{#if step.complete && store.proposing && i === store.steps.length - 1}
			<div class="proposing panel">
				<span class="spinner"></span>
				Proposing next step…
			</div>
		{/if}
	{/each}
	{#if store.steps.length === 0 && store.status === 'running'}
		<div class="proposing panel">
			<span class="spinner"></span>
			Starting optimization…
		</div>
	{/if}
{:else if kind}
	<section class="panel">
		<h2>Results</h2>
		<AggregateBar {store} {complete} />
		{#each store.flatTrialIds as trialId (trialId)}
			{@const entry = store.trialsById.get(trialId)}
			{#if entry}
				<TrialRow
					trial={entry.trial}
					scorings={entry.scorings}
					expanded={expandedTrials.has(trialId)}
					onToggle={() => toggleTrial(trialId)}
				/>
			{/if}
		{/each}
		{#if store.flatTrialIds.length === 0 && store.status === 'running'}
			<p class="muted">Waiting for trials…</p>
		{/if}
	</section>
{/if}

{#if complete || store.summary}
	<JobSummary summary={store.summary} {store} {complete} />
{/if}
