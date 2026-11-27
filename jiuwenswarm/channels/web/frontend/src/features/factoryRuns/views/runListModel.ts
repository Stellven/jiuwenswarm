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

export function contractDemoRuns(runs: Run[]) {
  const contracts = new Map<string, Run>();
  for (const run of runs) {
    if (!run.contract_demo) continue;
    const previous = contracts.get(run.task_id);
    if (!previous || (run.live_demo && !previous.live_demo) ||
        (Boolean(previous.live_demo) === Boolean(run.live_demo) && run.updated > previous.updated)) {
      contracts.set(run.task_id, run);
    }
  }
  return [...contracts.values()]
    .sort((a, b) => (a.demo_order ?? 0) - (b.demo_order ?? 0) || a.name.localeCompare(b.name));
}

/** Curated demo replays first (in their declared order); every other run below. */
export function groupRunEntries(entries: Entry[], showEverything = false) {
  const featured = entries.filter(({ run }) => run.featured);
  const history = entries.filter(({ run }) => run.read_only && !run.featured && !run.demo);
  const demo = entries
    .filter(({ run }) => run.demo && !run.featured)
    .sort((a, b) => (a.run.demo_order ?? 0) - (b.run.demo_order ?? 0) || a.run.name.localeCompare(b.run.name));
  const others = entries.filter(({ run }) => !run.featured && !run.demo && !run.read_only);
  const rest = showEverything ? others : others.filter(({ run }) => !run.scratch && !run.duplicate);
  return { featured, history, demo, rest, hidden: others.length - rest.length };
}
