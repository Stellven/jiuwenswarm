// Capsule display names aligned with the component atlas. One data file in the
// repository (factory/ccs/atlas-names.json) drives both the backend catalog and
// the labels the UI needs before the catalog loads (arms, overview, timeline).
import atlas from '../../../../../../../factory/ccs/atlas-names.json' with { type: 'json' };

export const ccKinds = ['builder', 'tool', 'analysis', 'factory'] as const;
export type CcKind = (typeof ccKinds)[number];

export type AtlasName = {
  capsule_id: string;
  title: string;
  kind: CcKind;
  atlas_cc_id: string | null;
  component: string | null;
  target: string | null;
  summary: string;
  former_names?: string[];
};

export type KindLegend = Record<CcKind, { label: string; naming: string; plain: string }>;

const entries = atlas.capsules as Record<string, AtlasName>;
export const kindLegend = atlas.kinds as KindLegend;
export const kindLegendZh: Record<CcKind, string> = {
  builder: '为一个引擎组件编写源代码。能力胶囊是构建代码的方法，而不是组件本身。',
  tool: '运行现有的工具、实验或运行器，返回经过验证的回执或产物；不编写产品源代码。',
  analysis: '读取追踪、计数器和性能剖析等证据，给出可由验证器复算的结论；不编写产品源代码。',
  factory: '执行软件工厂中的一个步骤（简报、契约、工单、集成、镜像或结论），并交付其产物。',
};

const byKey = new Map<string, { directory: string; entry: AtlasName }>();
for (const [directory, entry] of Object.entries(entries)) {
  const leaf = directory.split('/').pop() || directory;
  for (const key of [entry.capsule_id, directory, leaf, entry.atlas_cc_id]) {
    if (key && !byKey.has(key.toLowerCase())) byKey.set(key.toLowerCase(), { directory, entry });
  }
}
// Longest ids first so "factory.lab_client.submit" resolves to factory.lab_client.
const ids = [...byKey.keys()].filter((key) => key.includes('.')).sort((a, b) => b.length - a.length);

/** Resolve a capsule directory, leaf name, cc.yaml id, atlas id or qualified capability call. */
export function atlasName(reference: string | null | undefined): AtlasName | undefined {
  if (!reference) return undefined;
  const key = reference.split('@', 1)[0].trim().toLowerCase();
  const direct = byKey.get(key);
  if (direct) return direct.entry;
  const prefix = ids.find((id) => key.startsWith(id + '.'));
  return prefix ? byKey.get(prefix)?.entry : undefined;
}

export function atlasTitle(reference: string | null | undefined): string | undefined {
  return atlasName(reference)?.title;
}

export function isCcKind(value: unknown): value is CcKind {
  return typeof value === 'string' && (ccKinds as readonly string[]).includes(value);
}

/** "Builds the code for the expert weight cache component in llama.cpp." */
export function builderSubtitle(entry: Pick<AtlasName, 'component' | 'target'> | undefined): string | undefined {
  if (!entry?.component) return undefined;
  const component = entry.component.replace(/^[A-Z](?![A-Z])/, (letter) => letter.toLowerCase());
  return `Builds the code for the ${component} component${entry.target ? ` in ${entry.target}` : ''}.`;
}

export function builderSubtitleZh(entry: Pick<AtlasName, 'component' | 'target'> | undefined): string | undefined {
  if (!entry?.component) return undefined;
  return `为${entry.target ? ` ${entry.target} 中的` : ''}「${entry.component}」组件构建代码。`;
}
