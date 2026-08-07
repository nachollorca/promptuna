<script lang="ts">
	interface Props {
		label: string;
		/** Collapsed by default unless open=true. */
		open?: boolean;
		/** Sub-label shown next to the header (e.g. "JSON", count). */
		hint?: string;
		children: import('svelte').Snippet;
	}

	let { label, open = false, hint, children }: Props = $props();
</script>

<section class="collapsible">
	<button type="button" class="head" onclick={() => (open = !open)} aria-expanded={open}>
		<span class="chev">{open ? '▾' : '▸'}</span>
		<span class="label">{label}</span>
		{#if hint}<span class="hint">{hint}</span>{/if}
	</button>
	{#if open}
		<div class="body">
			{@render children()}
		</div>
	{/if}
</section>

<style>
	.collapsible {
		margin-top: var(--space-md);
	}

	.head {
		display: flex;
		align-items: baseline;
		gap: var(--space-xs);
		width: 100%;
		border: 1px solid var(--border);
		background: var(--surface-secondary);
		padding: 4px var(--space-sm);
		text-align: left;
	}

	.head:hover {
		background: var(--surface-dim);
	}

	.chev {
		font-family: var(--font-mono);
		font-size: 10px;
		color: var(--muted);
	}

	.label {
		font-family: var(--font-mono);
		font-size: 11px;
		font-weight: 500;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--muted);
	}

	.hint {
		font-family: var(--font-mono);
		font-size: 10px;
		color: var(--muted);
		opacity: 0.7;
		margin-left: var(--space-xs);
	}

	.body {
		margin-top: var(--space-sm);
	}
</style>
