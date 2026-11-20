export type GuidedReplayPage = 'projects' | 'library' | 'compose' | 'scheduling' | 'construction' | 'product';

export function mountGuidedReplay(container: HTMLElement, data: unknown, initialPage?: GuidedReplayPage): () => void;
