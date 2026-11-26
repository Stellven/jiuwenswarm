export type PlannerTab = 'live' | 'ablation';

export type FactoryEntry =
  | { view: 'capabilityCapsules'; capsule?: string }
  | { view: 'planner'; plan?: string; tab?: PlannerTab }
  | {
      view: 'factoryRuns';
      /** Factory runs (default) or legacy planner section fallback. */
      section?: 'runs' | 'planner';
      run?: string;
      file?: string;
      /** A planning run id when section is planner. */
      plan?: string;
    };

export function capsuleHref(name?: string): string {
  return name ? `#capsules/${encodeURIComponent(name)}` : '#capsules';
}

export function runHref(run?: string, file?: string): string {
  if (!run) return '#factory-run';
  const query = file ? `?file=${encodeURIComponent(file)}` : '';
  return `#factory-run/${encodeURIComponent(run)}${query}`;
}

export function plannerHref(plan?: string, tab?: PlannerTab): string {
  const base = plan ? `#planner/${encodeURIComponent(plan)}` : '#planner';
  if (tab && tab !== 'live') {
    return `${base}?tab=${encodeURIComponent(tab)}`;
  }
  return base;
}

export function readFactoryEntry(hash: string): FactoryEntry | undefined {
  const match = /^#(capsules|factory-run|planner|factory-planner)(?:\/([^/?#]+))?(?:\?([^#]*))?$/.exec(hash);
  if (!match) return undefined;
  try {
    const id = match[2] ? decodeURIComponent(match[2]) : undefined;
    if (id && !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$/.test(id)) return undefined;
    if (match[1] === 'capsules') return { view: 'capabilityCapsules', capsule: id };
    if (match[1] === 'planner' || match[1] === 'factory-planner') {
      const rawTab = new URLSearchParams(match[3]).get('tab');
      const tab: PlannerTab | undefined =
        rawTab === 'live' || rawTab === 'ablation' ? rawTab : undefined;
      return { view: 'planner', plan: id, tab };
    }
    const file = new URLSearchParams(match[3]).get('file');
    return { view: 'factoryRuns', run: id, file: id && file ? file : undefined };
  } catch {
    return undefined;
  }
}
