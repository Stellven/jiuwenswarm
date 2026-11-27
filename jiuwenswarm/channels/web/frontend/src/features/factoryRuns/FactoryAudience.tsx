import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { FactoryRunsPage } from './FactoryRunsPage';
import { CapsulesPage } from './cc/CapsulesPage';
import { capsuleHref, readFactoryEntry, runHref } from './cc/navigation';
import { hasStaticRun, staticBuild } from './staticData';

function readAudienceEntry() {
  const entry = readFactoryEntry(window.location.hash);
  if (staticBuild && entry?.view === 'factoryRuns' && entry.run && !hasStaticRun(entry.run)) {
    window.history.replaceState(window.history.state, '', runHref());
    return undefined;
  }
  return entry;
}

export function FactoryAudience() {
  const [entry, setEntry] = useState(() => readAudienceEntry());
  useEffect(() => {
    const sync = () => setEntry(readAudienceEntry());
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);
  const activeNav = entry?.view ?? 'factoryRuns';
  return (
    <AppShell
      sidebar={{
        activeNav,
        showNewSession: false,
        hideUnavailableNavItems: staticBuild,
        hiddenNavItems: ['personalContext'],
        availableNavItems: ['factoryRuns', 'capabilityCapsules'],
        onNavigate(nav) {
          if (nav === 'factoryRuns' || nav === 'capabilityCapsules') {
            window.location.hash = nav === 'factoryRuns' ? runHref() : capsuleHref();
          }
        },
      }}
    >
      <main className="content" data-testid="app-audience-content">
        {staticBuild && (
          <p className="factory-static-copy" data-testid="factory-runs-static-copy">
            Static copy · Nov 27, 2026 · Runs 1–3
          </p>
        )}
        {entry?.view === 'capabilityCapsules' ? (
          <div className="app-section min-h-0" data-testid="app-capability-capsules">
            <CapsulesPage name={entry.capsule} />
          </div>
        ) : (
          <div className="app-section min-h-0" data-testid="app-factory-runs">
            <FactoryRunsPage entry={entry} engineViewer />
          </div>
        )}
      </main>
    </AppShell>
  );
}
