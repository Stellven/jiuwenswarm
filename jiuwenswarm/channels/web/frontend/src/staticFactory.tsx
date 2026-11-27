import ReactDOM from 'react-dom/client';
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { common, factoryRuns, nav } from './i18n/locales/en.json';
import { FactoryAudience } from './features/factoryRuns/FactoryAudience';
import { readFactoryEntry, runHref } from './features/factoryRuns/cc/navigation';
import './styles/foundation.css';
import './styles/themes/default/light.css';
import './index.css';
import './App.css';

if (!readFactoryEntry(window.location.hash)) {
  window.history.replaceState(window.history.state, '', runHref());
}

const root = ReactDOM.createRoot(document.getElementById('root')!);
void i18n
  .use(initReactI18next)
  .init({
    lng: 'en',
    fallbackLng: 'en',
    resources: { en: { translation: { common, factoryRuns, nav } } },
    interpolation: { escapeValue: false },
    showSupportNotice: false,
  })
  .then(() => root.render(<FactoryAudience />));
