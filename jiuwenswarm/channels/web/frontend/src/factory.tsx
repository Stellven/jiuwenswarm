import { createRoot } from 'react-dom/client';
import './i18n';
import './styles/themes/default/light.css';
import { CCWorkflowPanel } from './features/workflowDemo/CCWorkflowPanel';

createRoot(document.getElementById('root')!).render(<CCWorkflowPanel />);
