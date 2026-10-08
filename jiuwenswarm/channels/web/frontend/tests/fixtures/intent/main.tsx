/** Actual native ChatPanel/InputArea, with local application-context fixtures. */
import React from 'react';
import { createRoot } from 'react-dom/client';
import '../../../src/i18n';
import '../../../src/styles/foundation.css';
import '../../../src/styles/themes/default/light.css';
import '../../../src/index.css';
import { ChatPanel } from '../../../src/components/ChatPanel';
import { useChatStore, useSessionStore } from '../../../src/stores';
import { useCodexSubscription } from '../../../src/features/codexSubscription/state';

const session = 'native-intent-fixture';
useChatStore.getState().ensureRuntime(session);
useChatStore.getState().setActiveSessionId(session);
useSessionStore.getState().ensureRuntime(session);
useSessionStore.getState().setMode(session, 'agent');
useSessionStore.getState().setConnected(true);
useCodexSubscription.getState().set({ enabled: true, state: 'ready' });

createRoot(document.getElementById('root')!).render(
  <ChatPanel
    onSendMessage={(content) => {
      (window as unknown as { ordinaryMessage: string }).ordinaryMessage = content;
    }}
    onEnsureSession={async () => session}
    onForkSession={async () => {}}
    onPersistMedia={async () => ({})}
    onPersistDocuments={async () => ({})}
    onInterrupt={() => {}}
    onCancel={() => {}}
    onSwitchMode={() => {}}
    isProcessing={false}
    onUserAnswer={async () => true}
    permissionProfile="default"
    onSavePermission={async () => {}}
  />,
);
