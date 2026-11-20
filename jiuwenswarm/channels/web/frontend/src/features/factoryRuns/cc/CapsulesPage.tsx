import { useMemo, useState } from 'react';
import type { EvidenceFile } from '../api';
import { CapsuleHeadlineResults, useFinalHeadlines, type HeadlineRow } from '../FinalHeadlines';
import { capsuleApi, type CapsuleCard, type CapsuleCatalog, type CapsuleDetail } from './capsuleApi';
import { BuilderRunEvidence, CapsuleEvidenceView, Receipt } from './CapsuleEvidence';
import { Integrity, Loading, MaterialDialog, MaterialList, SafeMarkdown, StructuredData } from './CapsuleMaterial';
import { displayName, isRecord, markdownSections, plainDescription, readableName } from './capsuleModel';
import { type CopyKey, useCapsuleCopy } from './copy';
import { capsuleHref } from './navigation';
import { useCapsuleResource } from './useCapsuleResource';
import './capsules.css';

const catalogRequest = (mode: string, signal: AbortSignal) => capsuleApi.catalog(signal, mode === 'with-usage');
const tabs = ['method', 'ontology', 'acceptance', 'source', 'files', 'artifacts', 'contract'] as const;
type Tab = (typeof tabs)[number];

function kindLabel(kind: string): CopyKey | undefined {
  if (kind === 'builder' || kind === 'analysis') return kind;
  return kind === 'factory-support' ? 'supportKind' : undefined;
}

function CapsuleKind({ kind }: { kind: string }) {
  const copy = useCapsuleCopy();
  const label = kindLabel(kind);
  return <span className="cc-kind">{label ? copy(label) : readableName(kind)}</span>;
}

function Card({ capsule, results }: { capsule: CapsuleCard; results?: HeadlineRow[] }) {
  const copy = useCapsuleCopy();
  return (
    <a
      className="cc-card"
      href={capsuleHref(capsule.name)}
      data-testid="factory-runs-capsule-card"
      data-variant={capsule.name}
    >
      <div className="cc-card-meta">
        {capsule.starred ? (
          <span className="cc-star">
            <span aria-hidden>★</span> {copy('starred')}
          </span>
        ) : (
          <CapsuleKind kind={capsule.kind} />
        )}
        <Integrity state={capsule.integrity} />
      </div>
      <h3>{displayName(capsule)}</h3>
      <p>{plainDescription(capsule.description || capsule.component || capsule.id)}</p>
      {!!results?.length && <CapsuleHeadlineResults rows={results} />}
      {!!capsule.used_in_runs && (
        <small className="cc-run-count" data-testid="factory-runs-capsule-used">
          {copy('usedInRuns')} · {capsule.used_in_runs}
        </small>
      )}
      <div className="cc-card-footer">
        <code>{capsule.version ? `v${capsule.version}` : capsule.binding}</code>
        <span>{capsule.arm ? `${copy('arm')} ${capsule.arm}` : capsule.binding}</span>
        <span className="cc-card-arrow" aria-hidden>
          ↗
        </span>
      </div>
    </a>
  );
}

function CatalogView({ capsules, headlines }: { capsules: CapsuleCard[]; headlines: HeadlineRow[] }) {
  const copy = useCapsuleCopy();
  const [query, setQuery] = useState('');
  const [kind, setKind] = useState<'all' | 'builder' | 'analysis' | 'factory-support'>('all');
  const needle = query.trim().toLowerCase();
  const shown = capsules.filter(
    (capsule) =>
      (kind === 'all' || capsule.kind === kind) &&
      [
        capsule.name,
        capsule.id,
        displayName(capsule),
        capsule.description,
        capsule.component,
        capsule.strata_mechanism,
      ].some((value) => value?.toLowerCase().includes(needle)),
  );
  const groups = [
    {
      title: 'builders',
      rows: shown.filter((capsule) => capsule.starred).sort((a, b) => (a.arm || '').localeCompare(b.arm || '')),
    },
    { title: 'builder', rows: shown.filter((capsule) => !capsule.starred && capsule.kind === 'builder') },
    {
      title: 'featuredAnalysis',
      rows: shown
        .filter((capsule) => capsule.kind === 'analysis' && capsule.featured_analysis_at)
        .sort((a, b) => (b.featured_analysis_at || 0) - (a.featured_analysis_at || 0)),
    },
  ] as const;
  const support = shown.filter(
    (capsule) => !capsule.starred && capsule.kind !== 'analysis' && capsule.kind !== 'builder',
  );
  const library = shown.filter((capsule) => capsule.kind === 'analysis' && !capsule.featured_analysis_at);
  return (
    <>
      <header className="cc-catalog-header">
        <h1 data-testid="factory-runs-capsule-catalog-title">{copy('title')}</h1>
        <p>{copy('intro')}</p>
        <div className="cc-catalog-controls">
          <input
            type="search"
            placeholder={copy('search')}
            aria-label={copy('search')}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            data-testid="factory-runs-capsule-search"
          />
          <select
            value={kind}
            onChange={(event) => setKind(event.target.value as typeof kind)}
            aria-label={copy('kind')}
            data-testid="factory-runs-capsule-kind"
          >
            <option value="all">{copy('allKinds')}</option>
            <option value="builder">{copy('builder')}</option>
            <option value="analysis">{copy('analysis')}</option>
            <option value="factory-support">{copy('supportKind')}</option>
          </select>
        </div>
      </header>
      {groups
        .filter(({ rows }) => rows.length)
        .map(({ title, rows }) => (
          <section
            className="cc-catalog-group"
            key={title}
            data-testid="factory-runs-capsule-catalog-group"
            data-variant={title}
          >
            <div className="cc-catalog-group-title">
              <h2>{copy(title)}</h2>
              <span>{rows.length}</span>
            </div>
            <div className={title === 'builders' ? 'cc-grid cc-grid-stars' : 'cc-grid'}>
              {rows.map((capsule) => (
                <Card key={capsule.name} capsule={capsule} results={capsule.starred
                  ? headlines.filter((row) => row.cc === capsule.arm)
                  : undefined} />
              ))}
            </div>
          </section>
        ))}
      {library.length > 0 && (
        <details
          className="cc-catalog-group cc-library"
          open={!!needle}
          data-testid="factory-runs-capsule-analysis-library"
        >
          <summary className="cc-catalog-group-title">
            <h2>{copy('analysisLibrary')}</h2>
            <span>{library.length}</span>
          </summary>
          <div className="cc-grid">
            {library.map((capsule) => (
              <Card key={capsule.name} capsule={capsule} />
            ))}
          </div>
        </details>
      )}
      {support.length > 0 && (
        <section className="cc-catalog-group" data-testid="factory-runs-capsule-catalog-group" data-variant="support">
          <div className="cc-catalog-group-title">
            <h2>{copy('support')}</h2>
            <span>{support.length}</span>
          </div>
          <div className="cc-grid">
            {support.map((capsule) => (
              <Card key={capsule.name} capsule={capsule} />
            ))}
          </div>
        </section>
      )}
      {!shown.length && (
        <p className="cc-muted" role="status">
          {copy('noMatches')}
        </p>
      )}
    </>
  );
}

function CapsuleHeader({ capsule }: { capsule: CapsuleDetail }) {
  const copy = useCapsuleCopy();
  return (
    <header className="cc-hero" data-testid="factory-runs-capsule-header">
      <div className="cc-hero-text">
        <div className="cc-hero-labels">
          {capsule.starred && (
            <span className="cc-star">
              <span aria-hidden>★</span> {copy('starred')}
            </span>
          )}
          <CapsuleKind kind={capsule.kind} />
          {capsule.arm && (
            <span className="cc-kind">
              {copy('arm')} {capsule.arm}
            </span>
          )}
        </div>
        <h1 data-testid="factory-runs-capsule-title">{displayName(capsule)}</h1>
        <p>{plainDescription(capsule.description || capsule.verifier || '')}</p>
        <dl className="cc-meta">
          {capsule.component && (
            <div>
              <dt>{copy('component')}</dt>
              <dd>{capsule.component}</dd>
            </div>
          )}
          {capsule.subcomponent && (
            <div>
              <dt>{copy('subcomponent')}</dt>
              <dd>{capsule.subcomponent}</dd>
            </div>
          )}
          <div>
            <dt>{copy('capability')}</dt>
            <dd>
              <code>{capsule.id}</code>
            </dd>
          </div>
        </dl>
      </div>
      <div className="cc-release" data-testid="factory-runs-capsule-release">
        <div className="cc-split-row">
          <span>{copy('version')}</span>
          <strong>{capsule.version || '—'}</strong>
        </div>
        <div className="cc-split-row">
          <span>{copy('release')}</span>
          <Integrity state={capsule.integrity} />
        </div>
        <code className="cc-release-value">{capsule.digest || '—'}</code>
        {capsule.expected_digest && capsule.expected_digest !== capsule.digest && (
          <div className="cc-mismatch-digest">
            <span>{copy('expected')}</span>
            <code>{capsule.expected_digest}</code>
          </div>
        )}
      </div>
    </header>
  );
}

function DocumentSection({
  name,
  path,
  available,
  onOpen,
  excerpt,
}: {
  name: string;
  path?: string;
  available: Set<string>;
  onOpen: (path: string) => void;
  excerpt?: 'intro' | 'acceptance';
}) {
  const copy = useCapsuleCopy();
  const load = useMemo(
    () => (relative: string, signal: AbortSignal) => capsuleApi.file(name, relative, signal),
    [name],
  );
  const result = useCapsuleResource(path, load);
  if (!path) return <p className="cc-muted">{copy('unavailable')}</p>;
  if (!result.data) return <Loading {...result} />;
  const sections = excerpt ? markdownSections(result.data.content) : [];
  const section =
    excerpt === 'acceptance'
      ? sections.find(({ heading }) => /^done|^acceptance|^\d+\. score/i.test(heading))
      : sections[0];
  const content = excerpt ? section?.source || '' : result.data.content;
  return (
    <>
      <div className="cc-material-meta">
        <button
          className="cc-text-button"
          type="button"
          onClick={() => onOpen(path)}
          data-testid="factory-runs-capsule-document"
          data-variant={path}
        >
          {path}
        </button>
        <Integrity state={result.data.integrity} />
      </div>
      {result.data.truncated && <p className="cc-alert">{copy('truncated')}</p>}
      {content && <SafeMarkdown content={content} path={path} available={available} onOpen={onOpen} />}
    </>
  );
}

function Ontology({
  capsule,
  files,
  onOpen,
}: {
  capsule: CapsuleDetail;
  files: EvidenceFile[];
  onOpen: (path: string) => void;
}) {
  const copy = useCapsuleCopy();
  const ontology = isRecord(capsule.ontology) ? capsule.ontology : {};
  const entities = isRecord(ontology.entities) ? ontology.entities : {};
  const fields = [
    ['component', ontology.component ?? entities.component],
    ['capability', ontology.capabilities ?? ontology.capability ?? entities.capabilities],
    ['regions', ontology.regions ?? entities.regions],
    ['observations', ontology.observation_points ?? entities.observation_points],
    ['quantities', ontology.quantities ?? entities.quantities],
    ['relations', ontology.relations],
  ] as const;
  const ontologyFile = capsule.files.find((file) => file.path === capsule.sections.ontology);
  return (
    <>
      <section className="cc-section" data-testid="factory-runs-capsule-ontology-section">
        <h2>{copy('ontology')}</h2>
        {ontologyFile ? (
          <MaterialList files={[ontologyFile]} onOpen={onOpen} />
        ) : (
          <p className="cc-muted">{copy('unavailable')}</p>
        )}
        <div className="cc-ontology-grid">
          {fields
            .filter(([, value]) => value != null)
            .map(([key, value]) => (
              <div
                key={key}
                className="cc-ontology-card"
                data-testid="factory-runs-capsule-ontology-field"
                data-variant={key}
              >
                <h3>{copy(key)}</h3>
                <StructuredData value={value} tree={key === 'observations' || key === 'quantities'} />
              </div>
            ))}
        </div>
      </section>
      {files.length > 0 && (
        <section className="cc-section" data-testid="factory-runs-capsule-owner-ontology">
          <h2>{copy('ownerOntology')}</h2>
          <MaterialList files={files} onOpen={onOpen} />
        </section>
      )}
    </>
  );
}

function DetailView({ capsule, catalog }: { capsule: CapsuleDetail; catalog?: CapsuleCatalog }) {
  const copy = useCapsuleCopy();
  const [requestedTab, setTab] = useState<Tab>(capsule.kind === 'analysis' ? 'artifacts' : 'method');
  const [material, setMaterial] = useState<{ path: string; run?: string; title?: string }>();
  const sections = capsule.sections;
  const ownerFiles = capsule.starred ? (catalog?.owner_ontology ?? []) : [];
  const contract = capsule.contract_id && catalog?.contract?.id === capsule.contract_id ? catalog.contract : null;
  const contractFiles = [contract?.readable, contract?.raw].filter((file): file is EvidenceFile => !!file);
  const available = useMemo(
    () => new Set([...capsule.files, ...ownerFiles, ...contractFiles].map((file) => file.path)),
    [capsule.files, ownerFiles, contractFiles],
  );
  const onOpen = (path: string) => setMaterial({ path });
  const onArtifact = (run: string, path: string, title: string) => setMaterial({ path, run, title });
  const doc = { name: capsule.name, available, onOpen };
  const byFolder = (folder: string) => capsule.files.filter((file) => file.path.startsWith(`${folder}/`));
  const testFiles = capsule.files.filter((file) => file.path.startsWith('tests/') || /^test_.*\.py$/.test(file.path));
  const pinned = capsule.files.filter(
    (file) => file.expected_sha256 || file.integrity === 'mismatch' || file.integrity === 'missing',
  );
  const visibleTabs = tabs.filter(
    (tab) =>
      (tab !== 'ontology' || !!sections.ontology) &&
      (tab !== 'source' || !!sections.source_map || !!capsule.strata_mechanism) &&
      (tab !== 'contract' || !!capsule.contract_id) &&
      (tab !== 'acceptance' || !!capsule.verifier || !!sections.validation || testFiles.length > 0) &&
      (tab !== 'method' || !!sections.guide || !!sections.method),
  );
  const tab = visibleTabs.includes(requestedTab) ? requestedTab : visibleTabs[0];
  return (
    <>
      <a className="cc-back" href={capsuleHref()} data-testid="factory-runs-capsule-back">
        ← {copy('back')}
      </a>
      <CapsuleHeader capsule={capsule} />
      {capsule.kind === 'builder' && <BuilderRunEvidence capsule={capsule} onArtifact={onArtifact} />}
      <nav className="cc-tabs" aria-label={copy('title')} data-testid="factory-runs-capsule-tabs">
        {visibleTabs.map((item) => (
          <button
            key={item}
            type="button"
            aria-pressed={tab === item}
            onClick={() => setTab(item)}
            data-testid="factory-runs-capsule-tab"
            data-variant={item}
          >
            {copy(item)}
          </button>
        ))}
      </nav>
      <div className="cc-tab-body" data-testid="factory-runs-capsule-tab-content" data-variant={tab}>
        {tab === 'method' && (
          <>
            {sections.guide && (
              <section className="cc-section">
                <h2>{copy('guide')}</h2>
                <DocumentSection {...doc} path={sections.guide} excerpt="intro" />
              </section>
            )}
            {sections.method && (
              <section className="cc-section">
                <h2>{copy('verificationMethod')}</h2>
                <DocumentSection {...doc} path={sections.method} />
              </section>
            )}
          </>
        )}
        {tab === 'ontology' && <Ontology capsule={capsule} files={ownerFiles} onOpen={onOpen} />}
        {tab === 'source' && (
          <section className="cc-section">
            <h2>{copy('source')}</h2>
            {capsule.strata_mechanism && (
              <div className="cc-source-callout">
                <strong>{copy('mechanism')}</strong>
                <p>{capsule.strata_mechanism}</p>
              </div>
            )}
            <DocumentSection {...doc} path={sections.source_map} />
          </section>
        )}
        {tab === 'acceptance' && (
          <>
            {sections.guide && (
              <section className="cc-section">
                <h2>{copy('criteria')}</h2>
                <DocumentSection {...doc} path={sections.guide} excerpt="acceptance" />
              </section>
            )}
            {sections.profile && (
              <section className="cc-section">
                <h2>{copy('sparkProfile')}</h2>
                <DocumentSection {...doc} path={sections.profile} />
              </section>
            )}
            {sections.validation && (
              <section className="cc-section">
                <h2>{copy('tests')}</h2>
                <DocumentSection {...doc} path={sections.validation} />
              </section>
            )}
            <section className="cc-section">
              <h2>{copy('verifier')}</h2>
              <p>{capsule.verifier}</p>
              <MaterialList files={capsule.files.filter((file) => file.path === sections.verifier)} onOpen={onOpen} />
            </section>
            <section className="cc-section">
              <h2>{copy('latestReceipt')}</h2>
              <Receipt capsule={capsule} onArtifact={onArtifact} />
            </section>
            {testFiles.length > 0 && (
              <section className="cc-section">
                <h2>{copy('tests')}</h2>
                <MaterialList files={testFiles} onOpen={onOpen} />
              </section>
            )}
          </>
        )}
        {tab === 'files' && (
          <>
            {(
              [
                ['samples', byFolder('samples')],
                ['helpers', byFolder('helpers')],
                ['declarations', capsule.files.filter(({ path }) => !/^(samples|helpers)\//.test(path))],
              ] as const
            )
              .filter(([, files]) => files.length > 0)
              .map(([key, files]) => (
                <section className="cc-section" key={key}>
                  <h2>{copy(key)}</h2>
                  <MaterialList files={files} onOpen={onOpen} />
                </section>
              ))}
            {pinned.length > 0 && (
              <details className="cc-section cc-pinned" data-testid="factory-runs-capsule-pinned-hashes">
                <summary>
                  {copy('hashes')} ({pinned.length})
                </summary>
                <MaterialList files={pinned} onOpen={onOpen} hashes />
              </details>
            )}
          </>
        )}
        {tab === 'artifacts' && <CapsuleEvidenceView capsule={capsule} onArtifact={onArtifact} />}
        {tab === 'contract' && (
          <section className="cc-section">
            <h2>{capsule.contract_id}</h2>
            <MaterialList files={contractFiles} onOpen={onOpen} />
            <h3>{copy('coverage')}</h3>
            <dl className="cc-clauses">
              {capsule.contract_clauses.map((id) => {
                const clause = contract?.clauses.find((item) => item.id === id);
                return (
                  <div key={id} data-testid="factory-runs-capsule-contract-clause" data-variant={id}>
                    <dt>{clause?.title || readableName(id)}</dt>
                    <dd>{clause?.detail}</dd>
                  </div>
                );
              })}
            </dl>
          </section>
        )}
      </div>
      {material && (
        <MaterialDialog
          key={`${material.run || ''}:${material.path}`}
          name={capsule.name}
          path={material.path}
          run={material.run}
          title={material.title}
          available={available}
          onOpen={onOpen}
          onClose={() => setMaterial(undefined)}
        />
      )}
    </>
  );
}

export function CapsulesPage({ name }: { name?: string }) {
  const headlines = useFinalHeadlines(!name);
  const catalog = useCapsuleResource(name ? 'manifests-only' : 'with-usage', catalogRequest);
  const detail = useCapsuleResource(name, capsuleApi.detail);
  const copy = useCapsuleCopy();
  return (
    <div className="cc-page" data-testid="factory-runs-capsule-page" data-variant={name ? 'detail' : 'catalog'}>
      <div className="cc-shell">
        {name ? (
          detail.data ? (
            <DetailView key={detail.data.name} capsule={detail.data} catalog={catalog.data} />
          ) : (
            <>
              <a className="cc-back" href={capsuleHref()} data-testid="factory-runs-capsule-back">
                ← {copy('back')}
              </a>
              <Loading {...detail} />
            </>
          )
        ) : catalog.data ? (
          <CatalogView capsules={catalog.data.capsules} headlines={headlines?.payload.rows ?? []} />
        ) : (
          <Loading {...catalog} />
        )}
      </div>
    </div>
  );
}
