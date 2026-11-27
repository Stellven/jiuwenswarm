import { useEffect, useState } from 'react';
import { capsuleHref, readFactoryEntry, runHref } from './cc/navigation';
import { EngineCapsules } from './EngineCapsules';
import { EngineReport } from './EngineReport';
import { FactoryRunsPage } from './FactoryRunsPage';
import './engineSite.css';

export function EngineSite() {
  const [entry, setEntry] = useState(() => readFactoryEntry(window.location.hash || runHref()));
  useEffect(() => {
    const update = () => setEntry(readFactoryEntry(window.location.hash || runHref()));
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);

  return (
    <div className="engine-site" data-testid="factory-runs-engine-site">
      <header className="engine-site-header">
        <a className="engine-site-brand" href={runHref()} data-testid="factory-runs-engine-home">
          Inference Engine Factory
        </a>
        <nav aria-label="Inference Engine Factory" data-testid="factory-runs-engine-navigation">
          <a href={runHref()} aria-current={entry?.view === 'factoryRuns' ? 'page' : undefined} data-testid="factory-runs-engine-runs-link">Factory Runs</a>
          <a href={capsuleHref()} aria-current={entry?.view === 'capabilityCapsules' ? 'page' : undefined} data-testid="factory-runs-engine-capsules-link">Capability Capsules</a>
          <a href="#engine-report" aria-current={entry ? undefined : 'page'} data-testid="factory-runs-engine-report-link">Engine Report</a>
        </nav>
      </header>
      <main className="engine-site-main" key={entry?.view ?? 'report'}>
        {entry?.view === 'factoryRuns' ? (
          <FactoryRunsPage entry={entry} engineViewer />
        ) : entry?.view === 'capabilityCapsules' ? (
          <EngineCapsules name={entry.capsule} />
        ) : (
          <EngineReport />
        )}
      </main>
    </div>
  );
}
