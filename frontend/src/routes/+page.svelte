<script lang="ts">
	import { onDestroy } from 'svelte';
	import JobLauncher from '$lib/components/JobLauncher.svelte';
	import JobView from '$lib/components/JobView.svelte';
	import type { EventStoreState } from '$lib/types';
	import type { JobManifest } from '$lib/types';
	import { createJobSession, type JobSession } from '$lib/jobSession';

	let store = $state<EventStoreState | null>(null);
	let jobRunning = $derived(store?.status === 'running');

	let session: JobSession | null = null;

	function handleStarted(manifest: JobManifest) {
		session?.close();
		session = createJobSession(manifest, (next) => {
			store = next;
		});
	}

	onDestroy(() => session?.close());
</script>

<svelte:head>
	<title>Promptuna</title>
</svelte:head>

<JobLauncher disabled={jobRunning} onStarted={handleStarted} />

{#if store}
	<JobView {store} />
{/if}
