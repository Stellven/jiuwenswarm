import type { ComponentProps, ReactNode } from 'react';
import { SessionSidebar } from './SessionSidebar';

export function AppShell({ sidebar, children, sessionId }: {
  sidebar: ComponentProps<typeof SessionSidebar>;
  children: ReactNode;
  sessionId?: string;
}) {
  return (
    <div
      className={`shell shell--icon-rail ${sidebar.activeNav === 'agents' ? 'shell--agent-management' : ''}`}
      data-testid="app-shell"
      data-session-id={sessionId}
    >
      <SessionSidebar {...sidebar} />
      {children}
    </div>
  );
}
