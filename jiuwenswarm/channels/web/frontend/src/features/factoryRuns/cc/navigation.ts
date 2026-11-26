export type FactoryEntry =
  | { view: 'capabilityCapsules'; capsule?: string }
  | {
      view: 'factoryRuns';
      run?: string;
      file?: string;
      node?: string;
      panel?: 'contract';
    };

export function capsuleHref(name?: string): string {
  return name ? `#capsules/${encodeURIComponent(name)}` : '#capsules';
}

export function runHref(run?: string, file?: string): string {
  if (!run) return '#factory-run';
  const query = file ? `?file=${encodeURIComponent(file)}` : '';
  return `#factory-run/${encodeURIComponent(run)}${query}`;
}

export function nodeHref(run: string, node: string, panel?: 'contract'): string {
  return `${runHref(run)}?node=${encodeURIComponent(node)}${panel ? `&panel=${panel}` : ''}`;
}

export function readFactoryEntry(hash: string): FactoryEntry | undefined {
  const match = /^#(capsules|factory-run)(?:\/([^/?#]+))?(?:\?([^#]*))?$/.exec(hash);
  if (!match) return undefined;
  try {
    const id = match[2] ? decodeURIComponent(match[2]) : undefined;
    if (id && !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$/.test(id)) return undefined;
    if (match[1] === 'capsules') return { view: 'capabilityCapsules', capsule: id };
    const query = new URLSearchParams(match[3]);
    const file = query.get('file');
    const node = id && query.get('node');
    return {
      view: 'factoryRuns',
      run: id,
      file: id && file ? file : undefined,
      ...(node && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$/.test(node) ? { node } : {}),
      ...(node && query.get('panel') === 'contract' ? { panel: 'contract' } : {}),
    };
  } catch {
    return undefined;
  }
}
