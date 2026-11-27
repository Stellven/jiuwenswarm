import i18n from './i18n';
import ReactDOM from 'react-dom/client';
import { A2UIProvider } from '@a2ui/react';
import type { A2UIClientEventMessage } from '@a2ui/react';
import { injectStyles } from '@a2ui/react/styles';
import App from './App.tsx'
import { ShareImageExportRunner } from './features/shareImageExport'
import { openSourceSettingsPageDefinition } from './features/settings/registry/openSourceDefinition'
import type { SettingsRequest } from './features/settings/services/settingsContract'
import { dispatchA2UIAction } from './features/a2ui/actionBridge';
import { installDesktopLocalFilesBridge } from './features/workspace/localFilePicker';
import { readFactoryEntry, runHref } from './features/factoryRuns/cc/navigation';
import './styles/foundation.css'
import './styles/themes/default/light.css'
import './index.css'
import './features/a2ui/a2ui.css'

function flagA2UIIconFontAvailability() {
  if (typeof document === 'undefined' || !('fonts' in document)) {
    return
  }

  const fonts = document.fonts
  const hasMaterialSymbols =
    fonts.check('20px "Material Symbols Outlined"') ||
    fonts.check('20px "Google Symbols"')

  document.documentElement.classList.toggle(
    'a2ui-material-symbols-unavailable',
    !hasMaterialSymbols
  )
}

function handleA2UIAction(message: A2UIClientEventMessage) {
  void dispatchA2UIAction(message);
}

function resolveOpenSourceSettingsRequest(request: SettingsRequest): SettingsRequest {
  return request
}

const runnerJobId = window.location.pathname === '/share-export-runner'
  ? new URLSearchParams(window.location.search).get('job_id')?.trim() || null
  : null

const root = ReactDOM.createRoot(document.getElementById('root')!);

if (import.meta.env.VITE_ENGINE_FACTORY === '1') {
  document.documentElement.lang = 'en';
  document.documentElement.dataset.theme = 'default';
  document.documentElement.dataset.colorMode = 'light';
  document.title = 'JiuwenSwarm';
  if (!readFactoryEntry(window.location.hash)) {
    window.history.replaceState(window.history.state, '', runHref());
  }
  void i18n.changeLanguage('en').then(() => {
    root.render(
      <App
        audience
        settingsPageDefinition={openSourceSettingsPageDefinition}
        resolveSettingsRequest={resolveOpenSourceSettingsRequest}
      />,
    );
  });
} else {
  // Install the desktop drop bridge before ChatPanel mounts.
  installDesktopLocalFilesBridge();
  injectStyles();
  flagA2UIIconFontAvailability();
  void document.fonts?.ready.then(flagA2UIIconFontAvailability);
  root.render(
    <A2UIProvider onAction={handleA2UIAction}>
      {runnerJobId ? (
        <ShareImageExportRunner jobId={runnerJobId} />
      ) : (
        <App
          settingsPageDefinition={openSourceSettingsPageDefinition}
          resolveSettingsRequest={resolveOpenSourceSettingsRequest}
        />
      )}
    </A2UIProvider>,
  );
}
