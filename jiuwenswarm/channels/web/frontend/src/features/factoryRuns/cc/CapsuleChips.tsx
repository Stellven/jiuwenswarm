import { createContext, useContext, useMemo } from 'react';
import type { CapsuleCard } from './capsuleApi';
import { displayName, findCapsules } from './capsuleModel';
import { capsuleHref } from './navigation';
import './capsules.css';

export const CapsuleLinksContext = createContext<CapsuleCard[]>([]);

export function CapsuleChips({ value, label }: { value: unknown; label?: string }) {
  const catalog = useContext(CapsuleLinksContext);
  const linked = useMemo(() => findCapsules(value, catalog), [value, catalog]);
  if (!linked.length) return null;
  return (
    <span className="cc-chips" data-testid="factory-runs-capsule-chips">
      {linked.map((capsule) => (
        <a
          className="cc-chip"
          key={capsule.name}
          href={capsuleHref(capsule.name)}
          data-testid="factory-runs-capsule-chip"
          data-variant={capsule.name}
          title={capsule.id}
        >
          {capsule.starred && <span aria-hidden>★</span>}
          {label && linked.length === 1 ? label : displayName(capsule)}
        </a>
      ))}
    </span>
  );
}
