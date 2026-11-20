import type { Run } from '../api';

export function runListEntries(runs: Run[]) {
  const byId = new Map<string, Run>();
  for (const run of runs) {
    const previous = byId.get(run.id);
    if (!previous || run.updated >= previous.updated) byId.set(run.id, run);
  }

  const records = [...byId.values()];
  const titleCounts = new Map<string, number>();
  const sourceCounts = new Map<string, number>();
  const sourceKey = (run: Run) => JSON.stringify([run.name, run.kind, run.source_name, Math.floor(run.updated / 60)]);
  for (const run of records) {
    const key = sourceKey(run);
    titleCounts.set(run.name, (titleCounts.get(run.name) ?? 0) + 1);
    sourceCounts.set(key, (sourceCounts.get(key) ?? 0) + 1);
  }
  return records.map((run) => ({
    run,
    source: (titleCounts.get(run.name) ?? 0) > 1 ? run.source_name : undefined,
    shortId: (sourceCounts.get(sourceKey(run)) ?? 0) > 1 ? run.id.slice(0, 8) : undefined,
  }));
}

type Entry = ReturnType<typeof runListEntries>[number];

/** Curated demo replays first (in their declared order); every other run below. */
export function groupRunEntries(entries: Entry[], showEverything = false) {
  const demo = entries
    .filter(({ run }) => run.demo)
    .sort((a, b) => (a.run.demo_order ?? 0) - (b.run.demo_order ?? 0) || a.run.name.localeCompare(b.run.name));
  const others = entries.filter(({ run }) => !run.demo);
  const rest = showEverything ? others : others.filter(({ run }) => !run.scratch && !run.duplicate);
  return { demo, rest, hidden: others.length - rest.length };
}
