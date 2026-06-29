<script lang="ts" module>
	export type SelectOption = { value: string; label: string };
</script>

<script lang="ts">
	interface Props {
		value: string;
		options: SelectOption[];
		id?: string;
		placeholder?: string;
		disabled?: boolean;
		onchange?: () => void;
	}

	let {
		value = $bindable(),
		options,
		id,
		placeholder,
		disabled = false,
		onchange
	}: Props = $props();

	let root: HTMLDivElement | undefined = $state();
	let open = $state(false);
	let highlight = $state(-1);

	const selectedLabel = $derived(options.find((o) => o.value === value)?.label ?? value);

	function openList() {
		if (disabled) return;
		open = true;
		highlight = Math.max(
			0,
			options.findIndex((o) => o.value === value)
		);
	}

	function close() {
		open = false;
		highlight = -1;
	}

	function choose(option: SelectOption) {
		value = option.value;
		close();
		onchange?.();
	}

	function onKeydown(e: KeyboardEvent) {
		if (disabled) return;
		if (!open) {
			if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
				e.preventDefault();
				openList();
			}
			return;
		}
		switch (e.key) {
			case 'ArrowDown':
				e.preventDefault();
				highlight = Math.min(options.length - 1, highlight + 1);
				break;
			case 'ArrowUp':
				e.preventDefault();
				highlight = Math.max(0, highlight - 1);
				break;
			case 'Home':
				e.preventDefault();
				highlight = 0;
				break;
			case 'End':
				e.preventDefault();
				highlight = options.length - 1;
				break;
			case 'Enter':
				e.preventDefault();
				if (options[highlight]) choose(options[highlight]);
				break;
			case 'Escape':
				e.preventDefault();
				close();
				break;
			case 'Tab':
				close();
				break;
		}
	}

	// Close on outside click / focus loss.
	$effect(() => {
		if (!open) return;
		const onDoc = (e: MouseEvent) => {
			if (root && !root.contains(e.target as Node)) close();
		};
		document.addEventListener('mousedown', onDoc);
		return () => document.removeEventListener('mousedown', onDoc);
	});
</script>

<div class="select-root" bind:this={root}>
	<button
		{id}
		type="button"
		class="select-trigger"
		class:open
		{disabled}
		aria-haspopup="listbox"
		aria-expanded={open}
		onclick={openList}
		onkeydown={onKeydown}
	>
		<span class="select-value" class:placeholder={!selectedLabel && placeholder}>
			{selectedLabel || placeholder || ''}
		</span>
		<span class="select-chevron" class:up={open} aria-hidden="true"></span>
	</button>

	{#if open}
		<ul class="select-list" role="listbox" tabindex="-1">
			{#each options as option, i (option.value)}
				<li role="option" aria-selected={option.value === value}>
					<button
						type="button"
						class="select-option"
						class:highlighted={i === highlight}
						class:selected={option.value === value}
						onmouseenter={() => (highlight = i)}
						onclick={() => choose(option)}
					>
						{option.label}
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.select-root {
		position: relative;
	}

	.select-trigger {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-sm);
		width: 100%;
		padding: var(--space-sm) var(--space-sm);
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text);
		font-family: var(--font-sans);
		font-size: 14px;
		line-height: 20px;
		text-align: left;
		cursor: pointer;
	}

	.select-trigger:hover:not(:disabled) {
		border-color: var(--slate-900);
	}

	/* Elevation via border weight, matching the design-system focus rule. */
	.select-trigger:focus-visible,
	.select-trigger.open {
		outline: none;
		border-width: 2px;
		border-color: var(--slate-900);
	}

	.select-trigger:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.select-value {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.select-value.placeholder {
		color: var(--muted);
	}

	/* Sharp chevron drawn with borders — rotates on open. */
	.select-chevron {
		flex: none;
		width: 7px;
		height: 7px;
		border-right: 1.5px solid var(--slate-600);
		border-bottom: 1.5px solid var(--slate-600);
		transform: rotate(45deg) translateY(-2px);
		transition: transform 0.12s ease;
	}

	.select-chevron.up {
		transform: rotate(-135deg) translateY(-2px);
	}

	/* Popover — tonal layer, 1px border, no shadow, sharp corners. */
	.select-list {
		position: absolute;
		z-index: 20;
		top: calc(100% + 2px);
		left: 0;
		min-width: 100%;
		max-height: 240px;
		overflow-y: auto;
		margin: 0;
		padding: 0;
		list-style: none;
		background: var(--surface);
		border: 1px solid var(--slate-900);
	}

	.select-option {
		display: block;
		width: 100%;
		padding: var(--space-sm);
		border: none;
		background: transparent;
		color: var(--text);
		font-family: var(--font-sans);
		font-size: 14px;
		line-height: 20px;
		text-align: left;
		cursor: pointer;
	}

	/* Hover/keyboard highlight = active surface (Slate-100). */
	.select-option.highlighted,
	.select-option:hover {
		background: var(--surface-dim);
	}

	/* Selected item = Slate-Navy primary, white text — replaces the OS blue. */
	.select-option.selected {
		background: var(--primary);
		color: var(--on-primary);
	}

	.select-option.selected:hover,
	.select-option.selected.highlighted {
		background: var(--primary-hover);
		color: var(--on-primary);
	}
</style>
