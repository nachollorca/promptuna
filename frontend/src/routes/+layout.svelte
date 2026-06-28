<script lang="ts">
	import { resolve } from '$app/paths';
	import '../app.css';

	let { children } = $props();
</script>

<div class="app-shell">
	<header class="app-header">
		<h1><a href={resolve('/')}>Promptuna</a></h1>
		<nav>
			<a href={resolve('/')}>New job</a>
			<a href={resolve('/jobs')}>Jobs</a>
		</nav>
	</header>
	<main class="app-main">
		{@render children()}
	</main>
</div>
