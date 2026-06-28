<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { page } from '$app/stores';
	import JobView from '$lib/components/JobView.svelte';
	import type { EventStoreState } from '$lib/types';
	import { createJobSession, loadReplayJob } from '$lib/jobSession';

	let store = $state<EventStoreState | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);

	let session: { close: () => void } | null = null;

	onMount(async () => {
		const jobId = $page.params.id;
		if (!jobId) {
			error = 'Missing job id';
			loading = false;
			return;
		}
		try {
			const initial = await loadReplayJob(jobId);
			store = initial;

			if (initial.status === 'running') {
				session = createJobSession(initial.manifest!, (next) => {
					store = next;
				});
			}
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			loading = false;
		}
	});

	onDestroy(() => session?.close());
</script>

<svelte:head>
	<title>Job {$page.params.id} — Promptuna</title>
</svelte:head>

{#if loading}
	<p class="muted">Loading job…</p>
{:else if error}
	<div class="error-banner panel">{error}</div>
{:else if store}
	<JobView {store} />
{/if}
