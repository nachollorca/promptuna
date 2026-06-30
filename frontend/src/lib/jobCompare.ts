import type { JobKind, JobListItem, JobManifest } from '$lib/types';

/** Fields that must match for two jobs to be comparable side by side. */
export interface ComparableJob {
	kind: JobKind;
	project: string;
	examples: string;
	metrics: string[] | null;
	dataset_sha256?: string;
}

export interface CompareMismatch {
	field: string;
	values: string[];
}

const MAX_COMPARE_JOBS = 4;
const MIN_COMPARE_JOBS = 2;

export function metricsKey(metrics: string[] | null | undefined): string {
	if (!metrics || metrics.length === 0) return '';
	return [...metrics].sort().join('\0');
}

export function comparableFromListItem(job: JobListItem): ComparableJob {
	return {
		kind: job.kind,
		project: job.project,
		examples: job.examples,
		metrics: job.metrics
	};
}

export function comparableFromManifest(manifest: JobManifest): ComparableJob {
	return {
		kind: manifest.kind,
		project: manifest.project,
		examples: manifest.examples,
		metrics: manifest.metrics ?? null,
		dataset_sha256: manifest.dataset_sha256
	};
}

function formatField(job: ComparableJob, key: keyof ComparableJob): string {
	const value = job[key];
	if (key === 'metrics') {
		const metrics = job.metrics;
		return metrics && metrics.length > 0 ? metrics.join(', ') : '(none)';
	}
	return value == null || value === '' ? '—' : String(value);
}

export function findCompareMismatches(jobs: ComparableJob[]): CompareMismatch[] {
	if (jobs.length < 2) return [];

	const ref = jobs[0]!;
	const mismatches: CompareMismatch[] = [];

	const checks: Array<{
		label: string;
		match: (a: ComparableJob, b: ComparableJob) => boolean;
	}> = [
		{ label: 'kind', match: (a, b) => a.kind === b.kind },
		{ label: 'project', match: (a, b) => a.project === b.project },
		{ label: 'dataset', match: (a, b) => a.examples === b.examples },
		{
			label: 'metrics',
			match: (a, b) => metricsKey(a.metrics) === metricsKey(b.metrics)
		}
	];

	for (const { label, match } of checks) {
		if (!jobs.every((job) => match(ref, job))) {
			const key: keyof ComparableJob =
				label === 'dataset'
					? 'examples'
					: label === 'metrics'
						? 'metrics'
						: (label as keyof ComparableJob);
			mismatches.push({
				field: label,
				values: jobs.map((job) => formatField(job, key))
			});
		}
	}

	const sha256s = jobs.map((job) => job.dataset_sha256).filter((v): v is string => Boolean(v));
	if (sha256s.length === jobs.length && new Set(sha256s).size > 1) {
		mismatches.push({
			field: 'dataset (content)',
			values: sha256s
		});
	}

	return mismatches;
}

export function areJobsComparable(jobs: ComparableJob[]): boolean {
	return findCompareMismatches(jobs).length === 0;
}

export function canAddToComparison(selected: ComparableJob[], candidate: ComparableJob): boolean {
	if (selected.length === 0) return true;
	if (selected.length >= MAX_COMPARE_JOBS) return false;
	return areJobsComparable([...selected, candidate]);
}

export function compareJobLimits(): { min: number; max: number } {
	return { min: MIN_COMPARE_JOBS, max: MAX_COMPARE_JOBS };
}

export function formatCompareMismatchError(mismatches: CompareMismatch[]): string {
	const lines = mismatches.map((m) => {
		const detail = m.values.map((v, i) => `#${i + 1}: ${v}`).join('; ');
		return `${m.field} — ${detail}`;
	});
	return `Selected jobs are not comparable:\n${lines.join('\n')}`;
}
