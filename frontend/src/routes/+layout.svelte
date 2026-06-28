<script lang="ts">
	import { resolve } from '$app/paths';
	import '../app.css';

	let { children } = $props();
</script>

<div class="app-shell">
	<header class="app-header">
		<div class="app-brand">
			<span class="app-eyebrow">LLM · OPTIMIZATION LAB</span>
			<h1><a href={resolve('/')}>Promptuna</a></h1>
		</div>
		<nav>
			<a href={resolve('/')}>New job</a>
			<a href={resolve('/jobs')}>Jobs</a>
		</nav>
	</header>
	<main class="app-main">
		{@render children()}
	</main>
</div>

<style>
	.app-brand {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.app-eyebrow {
		font-family: var(--font-mono);
		font-size: 11px;
		font-weight: 500;
		line-height: 16px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--accent-teal);
	}

	.app-brand h1 {
		margin: 0;
	}
</style>
