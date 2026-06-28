<script lang="ts">
	import { onMount } from 'svelte';
	import { ApiError, fetchCatalog, startEvaluate, startOptimize, startRun } from '$lib/api';
	import type {
		CatalogProject,
		CatalogResponse,
		JobManifest,
		Operation,
		OptimizeRequest,
		RunRequest
	} from '$lib/types';
	import {
		loadRecentModels,
		loadRecentProposerModels,
		rememberModel,
		rememberProposerModel
	} from '$lib/recentModels';

	interface Props {
		disabled?: boolean;
		onStarted: (manifest: JobManifest) => void;
		onConflict?: () => void;
	}

	let { disabled = false, onStarted, onConflict }: Props = $props();

	let catalog = $state<CatalogResponse | null>(null);
	let loadError = $state<string | null>(null);
	let submitError = $state<string | null>(null);
	let submitting = $state(false);

	let operation = $state<Operation>('run');
	let projectName = $state('');
	let program = $state('');
	let prompt = $state('');
	let examples = $state('');
	let model = $state('');
	let workers = $state(1);
	let steps = $state(1);
	let proposerModel = $state('');
	let selectedMetrics = $state<string[]>([]);

	const selectedProject = $derived(catalog?.projects.find((p) => p.name === projectName) ?? null);

	onMount(async () => {
		const recent = loadRecentModels();
		const recentProposer = loadRecentProposerModels();
		if (recent[0]) model = recent[0];
		if (recentProposer[0]) proposerModel = recentProposer[0];

		try {
			catalog = await fetchCatalog();
			if (catalog.projects.length > 0) {
				selectProject(catalog.projects[0]);
			}
		} catch (err) {
			loadError = err instanceof Error ? err.message : String(err);
		}
	});

	function selectProject(project: CatalogProject) {
		projectName = project.name;
		program = project.programs[0] ?? '';
		prompt = project.prompts[0] ?? '';
		examples = project.datasets[0] ?? '';
		selectedMetrics = project.metrics.length > 0 ? [project.metrics[0]] : [];
	}

	function onProjectChange() {
		const project = catalog?.projects.find((p) => p.name === projectName);
		if (project) selectProject(project);
	}

	function toggleMetric(metric: string) {
		if (selectedMetrics.includes(metric)) {
			selectedMetrics = selectedMetrics.filter((m) => m !== metric);
		} else {
			selectedMetrics = [...selectedMetrics, metric];
		}
	}

	function buildManifest(jobId: string): JobManifest {
		const base = {
			job_id: jobId,
			kind: operation,
			status: 'running' as const,
			started_at: new Date().toISOString(),
			project: projectName,
			program,
			prompt,
			examples,
			model,
			workers
		};
		if (operation === 'evaluate') {
			return { ...base, metrics: [...selectedMetrics] };
		}
		if (operation === 'optimize') {
			return {
				...base,
				metrics: [...selectedMetrics],
				steps,
				proposer_model: proposerModel
			};
		}
		return base;
	}

	async function submit() {
		submitError = null;
		submitting = true;
		try {
			rememberModel(model);
			const body: RunRequest = {
				project: projectName,
				program,
				prompt,
				model,
				examples,
				workers
			};

			let jobId: string;
			if (operation === 'run') {
				({ job_id: jobId } = await startRun(body));
			} else if (operation === 'evaluate') {
				if (selectedMetrics.length === 0) {
					submitError = 'Select at least one metric';
					return;
				}
				({ job_id: jobId } = await startEvaluate({ ...body, metrics: selectedMetrics }));
			} else {
				if (selectedMetrics.length === 0) {
					submitError = 'Select at least one metric';
					return;
				}
				rememberProposerModel(proposerModel);
				({ job_id: jobId } = await startOptimize({
					...body,
					metrics: selectedMetrics,
					steps,
					proposer_model: proposerModel
				} as OptimizeRequest));
			}

			onStarted(buildManifest(jobId));
		} catch (err) {
			if (err instanceof ApiError && err.status === 409) {
				submitError =
					'Another job is already running. Wait for it to finish or open the jobs list.';
				onConflict?.();
			} else {
				submitError = err instanceof Error ? err.message : String(err);
			}
		} finally {
			submitting = false;
		}
	}
</script>

<section class="panel">
	<h2>Launch job</h2>

	{#if loadError}
		<div class="error-banner">Failed to load catalog: {loadError}</div>
	{:else if !catalog}
		<p class="muted">Loading catalog…</p>
	{:else}
		<div class="operation-toggle">
			{#each ['run', 'evaluate', 'optimize'] as op (op)}
				<button
					type="button"
					class="op-btn"
					class:active={operation === op}
					onclick={() => (operation = op as Operation)}
				>
					{op}
				</button>
			{/each}
		</div>

		<form
			class="form-grid"
			onsubmit={(e) => {
				e.preventDefault();
				void submit();
			}}
		>
			<div class="field">
				<label for="project">Project</label>
				<select id="project" bind:value={projectName} onchange={onProjectChange}>
					{#each catalog.projects as project (project.name)}
						<option value={project.name}>{project.name}</option>
					{/each}
				</select>
			</div>
			<div class="field">
				<label for="program">Program</label>
				<select id="program" bind:value={program}>
					{#each selectedProject?.programs ?? [] as name (name)}
						<option value={name}>{name}</option>
					{/each}
				</select>
			</div>
			<div class="field">
				<label for="prompt">Prompt</label>
				<select id="prompt" bind:value={prompt}>
					{#each selectedProject?.prompts ?? [] as name (name)}
						<option value={name}>{name}</option>
					{/each}
				</select>
			</div>
			<div class="field">
				<label for="examples">Dataset</label>
				<select id="examples" bind:value={examples}>
					{#each selectedProject?.datasets ?? [] as name (name)}
						<option value={name}>{name}</option>
					{/each}
				</select>
			</div>
			<div class="field">
				<label for="model">Model</label>
				<input id="model" type="text" bind:value={model} placeholder="provider:model-id" required />
			</div>
			<div class="field">
				<label for="workers">Workers</label>
				<input id="workers" type="number" min="1" bind:value={workers} required />
			</div>

			{#if operation === 'optimize'}
				<div class="field">
					<label for="steps">Steps</label>
					<input id="steps" type="number" min="0" bind:value={steps} required />
				</div>
				<div class="field">
					<label for="proposer">Proposer model</label>
					<input
						id="proposer"
						type="text"
						bind:value={proposerModel}
						placeholder="provider:model-id"
						required
					/>
				</div>
			{/if}

			{#if operation !== 'run' && selectedProject}
				<div class="field metrics-field">
					<span class="field-label">Metrics</span>
					<div class="metrics-list">
						{#each selectedProject.metrics as metric (metric)}
							<label>
								<input
									type="checkbox"
									checked={selectedMetrics.includes(metric)}
									onchange={() => toggleMetric(metric)}
								/>
								{metric}
							</label>
						{/each}
					</div>
				</div>
			{/if}

			<div class="submit-row">
				<button type="submit" class="btn btn-primary" disabled={disabled || submitting}>
					{submitting ? 'Starting…' : `Start ${operation}`}
				</button>
			</div>
		</form>

		{#if submitError}
			<div class="error-banner">{submitError}</div>
		{/if}

		<p class="muted catalog-path">Projects root: {catalog.projects_root}</p>
	{/if}
</section>

<style>
	.operation-toggle {
		display: flex;
		gap: 0.35rem;
		margin-bottom: 1rem;
	}

	.op-btn {
		padding: 0.35rem 0.75rem;
		border: 1px solid var(--border);
		border-radius: 6px;
		background: #fff;
		text-transform: capitalize;
	}

	.op-btn.active {
		background: var(--accent);
		border-color: var(--accent);
		color: #fff;
	}

	.field-label {
		font-size: 0.8125rem;
		font-weight: 500;
		color: var(--muted);
	}

	.submit-row {
		grid-column: 1 / -1;
	}

	.catalog-path {
		margin: 0.75rem 0 0;
		word-break: break-all;
	}
</style>
