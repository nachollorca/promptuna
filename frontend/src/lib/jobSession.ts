import type { EventEnvelope, EventStoreState, JobManifest, JobSummary } from '$lib/types';
import {
	createEventStoreState,
	manifestFromRecord,
	reduceEvent,
	reduceEvents
} from '$lib/eventStore';
import { connectJobEvents, type SseHandle } from '$lib/sseClient';
import { fetchJob } from '$lib/api';

export interface JobSession {
	close: () => void;
}

export function createJobSession(
	manifest: JobManifest,
	onUpdate: (store: EventStoreState) => void
): JobSession {
	let store = createEventStoreState(manifest);
	onUpdate(store);

	let sse: SseHandle | null = connectJobEvents(
		manifest.job_id,
		(event) => {
			store = reduceEvent(store, event);
			if (event.type === 'error') {
				store = { ...store, status: 'error' };
			}
			onUpdate(store);
		},
		() => {
			void refreshSummary();
		},
		() => {
			void refreshSummary();
		}
	);

	async function refreshSummary() {
		try {
			const detail = await fetchJob(manifest.job_id);
			const updatedManifest = manifestFromRecord(detail.manifest);
			store = reduceEvents(
				store,
				detail.events as EventEnvelope[],
				updatedManifest,
				detail.summary as JobSummary | null
			);
			onUpdate(store);
		} catch {
			store = { ...store, status: 'done' };
			onUpdate(store);
		}
	}

	return {
		close: () => {
			sse?.close();
			sse = null;
		}
	};
}

export async function loadReplayJob(jobId: string): Promise<EventStoreState> {
	const detail = await fetchJob(jobId);
	const manifest = manifestFromRecord(detail.manifest);
	return reduceEvents(
		createEventStoreState(manifest),
		detail.events as EventEnvelope[],
		manifest,
		detail.summary as JobSummary | null
	);
}
