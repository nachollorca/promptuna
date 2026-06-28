const MODELS_KEY = 'promptuna.recentModels';
const PROPOSER_KEY = 'promptuna.recentProposerModels';

export function loadRecentModels(): string[] {
	return loadList(MODELS_KEY);
}

export function loadRecentProposerModels(): string[] {
	return loadList(PROPOSER_KEY);
}

export function rememberModel(model: string): void {
	remember(MODELS_KEY, model);
}

export function rememberProposerModel(model: string): void {
	remember(PROPOSER_KEY, model);
}

function loadList(key: string): string[] {
	if (typeof localStorage === 'undefined') return [];
	try {
		const raw = localStorage.getItem(key);
		if (!raw) return [];
		const parsed = JSON.parse(raw);
		return Array.isArray(parsed) ? parsed.filter((v) => typeof v === 'string') : [];
	} catch {
		return [];
	}
}

function remember(key: string, value: string): void {
	const trimmed = value.trim();
	if (!trimmed || typeof localStorage === 'undefined') return;
	const list = loadList(key).filter((item) => item !== trimmed);
	list.unshift(trimmed);
	localStorage.setItem(key, JSON.stringify(list.slice(0, 8)));
}
