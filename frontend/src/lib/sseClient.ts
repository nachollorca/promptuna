import { apiBaseUrl } from '$lib/api';
import type { EventEnvelope } from '$lib/types';

export interface SseHandle {
	close: () => void;
}

export function connectJobEvents(
	jobId: string,
	onEvent: (event: EventEnvelope) => void,
	onError?: (error: Error) => void,
	onComplete?: () => void
): SseHandle {
	const controller = new AbortController();
	let buffer = '';

	void (async () => {
		try {
			const response = await fetch(`${apiBaseUrl()}/api/jobs/${jobId}/events`, {
				signal: controller.signal,
				headers: { Accept: 'text/event-stream' }
			});

			if (!response.ok) {
				throw new Error(`SSE failed: ${response.status}`);
			}

			const reader = response.body?.getReader();
			if (!reader) {
				throw new Error('SSE response has no body');
			}

			const decoder = new TextDecoder();
			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() ?? '';

				for (const line of lines) {
					if (!line.startsWith('data: ')) continue;
					const json = line.slice(6).trim();
					if (!json) continue;
					try {
						onEvent(JSON.parse(json) as EventEnvelope);
					} catch (err) {
						onError?.(err instanceof Error ? err : new Error(String(err)));
					}
				}
			}

			if (buffer.startsWith('data: ')) {
				const json = buffer.slice(6).trim();
				if (json) {
					onEvent(JSON.parse(json) as EventEnvelope);
				}
			}

			onComplete?.();
		} catch (err) {
			if (controller.signal.aborted) return;
			onError?.(err instanceof Error ? err : new Error(String(err)));
		}
	})();

	return {
		close: () => controller.abort()
	};
}
