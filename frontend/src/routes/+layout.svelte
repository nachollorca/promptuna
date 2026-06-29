<script lang="ts">
	import { resolve } from '$app/paths';
	import '../app.css';

	let { children } = $props();
</script>

<div class="app-shell">
	<header class="app-header">
		<div class="app-brand">
			<img src="/favicon.png" alt="Promptuna" class="app-logo" />
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
		flex-direction: row;
		align-items: center;
		gap: var(--space-sm);
	}

	.app-logo {
		height: 32px;
		width: auto;
		display: block;
	}

	.app-brand h1 {
		margin: 0;
	}
</style>
