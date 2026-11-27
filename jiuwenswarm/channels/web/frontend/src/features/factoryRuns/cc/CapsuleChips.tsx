import { createContext, useContext, useMemo } from 'react';
import type { CapsuleCard } from './capsuleApi';
import { displayName, findCapsules } from './capsuleModel';
import { inferenceCapsules } from './inferenceCapsuleCopy';
import { capsuleHref } from './navigation';
import './capsules.css';

export const CapsuleLinksContext = createContext<CapsuleCard[]>([]);

export function CapsuleChips({ value, label, capsuleIds }: {
  value?: unknown;
  label?: string;
  /** Exact capsule bindings in display order, using public method titles. */
  capsuleIds?: readonly string[];
}) {
  const catalog = useContext(CapsuleLinksContext);
  const linked = useMemo(() => {
    if (!capsuleIds) return findCapsules(value, catalog);
    const byId = new Map(catalog.map((capsule) => [capsule.id, capsule]));
    return capsuleIds.flatMap((id) => byId.get(id) ?? []);
  }, [value, capsuleIds, catalog]);
  if (!linked.length) return null;
  return (
    <span className="cc-chips" data-testid="factory-runs-capsule-chips">
      {linked.map((capsule) => {
        const methodTitle = capsuleIds ? inferenceCapsules[capsule.id]?.title : undefined;
        return (
          <a
            className="cc-chip"
            key={capsule.name}
            href={capsuleHref(capsule.name)}
            data-testid="factory-runs-capsule-chip"
            data-variant={capsule.name}
            title={capsule.id}
          >
            {capsule.starred && <span aria-hidden>★</span>}
            {label && linked.length === 1 ? label : methodTitle ?? displayName(capsule)}
          </a>
        );
      })}
    </span>
  );
}
