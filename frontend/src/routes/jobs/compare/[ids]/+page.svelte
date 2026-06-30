<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { page } from '$app/stores';
	import { resolve } from '$app/paths';
	import JobView from '$lib/components/JobView.svelte';
	import {
		areJobsComparable,
		comparableFromManifest,
		formatCompareMismatchError,
		findCompareMismatches
	} from '$lib/jobCompare';
	import { createJobSession, loadReplayJob, type JobSession } from '$lib/jobSession';
	import type { EventStoreState } from '$lib/types';

	let stores = $state<EventStoreState[]>([]);
	let error = $state<string | null>(null);
	let loading = $state(true);

	let sessions: JobSession[] = [];

	onMount(async () => {
		const ids =
			$page.params.ids
				?.split(',')
				.map((id) => id.trim())
				.filter(Boolean) ?? [];

		if (ids.length < 2) {
			error = 'Select at least two jobs to compare.';
			loading = false;
			return;
		}

		try {
			const loaded = await Promise.all(ids.map((id) => loadReplayJob(id)));
			const comparables = loaded.map((store) => comparableFromManifest(store.manifest!));

			if (!areJobsComparable(comparables)) {
				error = formatCompareMismatchError(findCompareMismatches(comparables));
				loading = false;
				return;
			}

			stores = loaded;

			sessions = loaded
				.filter((store) => store.status === 'running' && store.manifest)
				.map((store) =>
					createJobSession(store.manifest!, (next) => {
						const jobId = next.manifest?.job_id;
						if (!jobId) return;
						stores = stores.map((current) => (current.manifest?.job_id === jobId ? next : current));
					})
				);
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			loading = false;
		}
	});

	onDestroy(() => {
		for (const session of sessions) {
			session.close();
		}
	});
</script>

<svelte:head>
	<title>Compare jobs — Promptuna</title>
</svelte:head>

<section class="compare-page">
	<header class="compare-header">
		<h2>Job comparison</h2>
		<a class="btn btn-ghost" href={resolve('/jobs')}>Back to jobs</a>
	</header>

	{#if loading}
		<p class="muted">Loading jobs…</p>
	{:else if error}
		<div class="error-banner panel">{error}</div>
	{:else}
		<div class="compare-grid" style:--compare-cols={stores.length}>
			{#each stores as store (store.manifest?.job_id)}
				<div class="compare-column">
					{#if store.manifest}
						<div class="compare-column-label mono">
							{store.manifest.job_id.slice(0, 8)}…
						</div>
					{/if}
					<JobView {store} />
				</div>
			{/each}
		</div>
	{/if}
</section>

<style>
	.compare-page {
		width: calc(100vw - 2 * var(--container-margin));
		max-width: 1600px;
		margin-inline: calc(50% - min(1600px, calc(100vw - 2 * var(--container-margin))) / 2);
	}

	.compare-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-md);
		margin-bottom: var(--space-lg);
	}

	.compare-header h2 {
		margin: 0;
	}

	.compare-grid {
		display: grid;
		grid-template-columns: repeat(var(--compare-cols, 2), minmax(0, 1fr));
		gap: var(--space-md);
		align-items: start;
	}

	.compare-column {
		min-width: 0;
	}

	.compare-column-label {
		margin-bottom: var(--space-sm);
		font-size: 12px;
		color: var(--muted);
	}

	.error-banner {
		white-space: pre-wrap;
	}

	@media (max-width: 900px) {
		.compare-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
