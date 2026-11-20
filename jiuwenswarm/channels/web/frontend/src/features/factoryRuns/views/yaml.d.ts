declare module 'js-yaml' {
  export const CORE_SCHEMA: unknown;

  export function load(
    source: string,
    options: { schema: unknown; maxDepth: number; maxTotalMergeKeys: number },
  ): unknown;
}
