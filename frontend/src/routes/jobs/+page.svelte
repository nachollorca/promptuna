<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchJobs } from '$lib/api';
	import type { JobListItem } from '$lib/types';

	let jobs = $state<JobListItem[]>([]);
	let error = $state<string | null>(null);
	let loading = $state(true);

	onMount(async () => {
		try {
			const response = await fetchJobs();
			jobs = response.jobs;
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			loading = false;
		}
	});
</script>

<svelte:head>
	<title>Jobs — Promptuna</title>
</svelte:head>

<section class="panel">
	<h2>Past jobs</h2>

	{#if loading}
		<p class="muted">Loading…</p>
	{:else if error}
		<div class="error-banner">{error}</div>
	{:else if jobs.length === 0}
		<p class="muted">No jobs yet.</p>
	{:else}
		<table class="job-table">
			<thead>
				<tr>
					<th>Job ID</th>
					<th>Kind</th>
					<th>Status</th>
					<th>Project</th>
					<th>Started</th>
				</tr>
			</thead>
			<tbody>
				{#each jobs as job (job.job_id)}
					<tr>
						<td><a href="/jobs/{job.job_id}">{job.job_id.slice(0, 8)}…</a></td>
						<td>{job.kind}</td>
						<td><span class="badge {job.status}">{job.status}</span></td>
						<td>{job.project}</td>
						<td>{job.started_at}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
</section>
