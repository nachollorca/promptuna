<script lang="ts">
	import '../app.css';

	let { children } = $props();
</script>

<div class="app-shell">
	<header class="app-header">
		<h1><a href="/">Promptuna</a></h1>
		<nav>
			<a href="/">New job</a>
			<a href="/jobs">Jobs</a>
		</nav>
	</header>
	<main class="app-main">
		{@render children()}
	</main>
</div>
