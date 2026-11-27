import { getApiBase } from '../../../utils/env';
import { staticBuild, staticJson } from '../staticData';
import { warmTolerance } from './inferenceCapsuleCopy';
import { useCapsuleResource } from './useCapsuleResource';

type FixtureResult = {
  status: 'complete' | 'stopped';
  model: { id: string; source: string; sha256: string; bytes: number; window_tokens: number };
  engine: { image_id: string; sha256: string };
  configurations: Partial<Record<'stock' | 'configured', {
    cached_tokens: number;
    prompt_tokens: number;
    checkpoints_max?: number;
  }>>;
};

const path = '/api/factory/capsules/kv_reuse_lab/fixture';
const loadFixture = async (_: string, signal: AbortSignal): Promise<FixtureResult | null> => {
  if (staticBuild) return staticJson<FixtureResult | null>(path, { signal });
  const response = await fetch(getApiBase() + path, { signal });
  if (!response.ok) throw new Error('Unable to read the CPU fixture receipt.');
  return response.json();
};
const settings = {
  stock: 'Built-in defaults',
  configured: 'Full sliding-window cache · 32 checkpoints',
} as const;

export function PrefixReuseEvidence() {
  const { data, error } = useCapsuleResource('prefix-reuse', loadFixture);
  const source = staticBuild ? './evidence/prefix-reuse' : getApiBase() + path;
  return (
    <section data-testid="factory-runs-prefix-reuse-evidence">
      <h3>Factory stage · CC verifier · CPU fixture</h3>
      <p>Checks the first cached-token count for a follow-up that shares a document longer than the model's attention window.</p>
      {data ? (
        <>
          <p>In this fixture: {data.model.id}, a {data.model.window_tokens}-token attention window,
            {' '}{Math.round(data.model.bytes / 1_000_000)} MB, and the delivered binary running on CPU.</p>
          {data.status === 'stopped' && <p role="status">The fixture stopped before both results were recorded.</p>}
          <ul>
            {(['stock', 'configured'] as const).map((key) => {
              const result = data.configurations[key];
              return result && (
                <li key={key} data-testid="factory-runs-prefix-reuse-fixture-result" data-variant={key}>
                  <strong>{settings[key]}</strong> · {result.cached_tokens.toLocaleString('en-US')} of{' '}
                  {result.prompt_tokens.toLocaleString('en-US')} follow-up tokens cached ·{' '}
                  <a href={`${source}/${key}${staticBuild ? '.log' : ''}`} target="_blank" rel="noreferrer">Log excerpt</a>
                </li>
              );
            })}
          </ul>
          {data.configurations.stock?.cached_tokens === 769 && data.configurations.stock.prompt_tokens === 788 &&
            data.configurations.configured?.cached_tokens === 769 && data.configurations.configured.prompt_tokens === 788 &&
            <p>{"Factory check: the stock prompt cache already reuses the document (769/788 tokens, same as with C's flags). C's extra flags were not needed; AQBC kept them as measured (+736 MiB KV)."}</p>}
          {data.configurations.stock?.checkpoints_max === 32 && <p>The stock log reported a default of 32 context checkpoints.</p>}
          <a href={`${source}/summary${staticBuild ? '.json' : ''}`} target="_blank" rel="noreferrer" data-testid="factory-runs-prefix-reuse-fixture-receipt">CPU fixture receipt and model digest</a>
        </>
      ) : <p role="status">{error ?? (data === null ? 'No verified CPU fixture receipt is available.' : 'Loading CPU fixture evidence…')}</p>}
      <h3>Runtime stage · Target trials</h3>
      <p>Phase 0 compares expert placement settings on a loaded engine. In this run, neither alternative earned an accepted gain.</p>
      <p>Phase 0b checks the server log for shared-prefix state on a real model. In this run, the p2048 follow-up reused 2,045 of 2,080 tokens.</p>
      <h3>Runtime stage · Lab acceptance</h3>
      <p>The lab agent runs the delivered test requirements for speed, reuse, and answer identity on the target.</p>
      <p><strong>In this run.</strong> {warmTolerance}</p>
    </section>
  );
}
