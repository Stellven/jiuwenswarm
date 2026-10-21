import { settingsNavigationIcons } from '../../../../assets/settings';
import type { SettingsModuleDefinition } from '../../registry/types';
import { FreeModelsSettings } from './FreeModelsSettings';
import { ModelsSettings } from './ModelsSettings';
import { SubscriptionSettings } from '../agent/ConversationSettings';

export const modelsModule: SettingsModuleDefinition = {
  id: 'models',
  titleKey: 'settingsPanel.categories.models',
  icon: settingsNavigationIcons.models,
  source: 'config',
  sections: [
    { id: 'chatgpt-subscription', separatedRows: true, items: [{ id: 'chatgpt-subscription', component: 'custom', render: SubscriptionSettings }] },
    {
      id: 'limited-free-models',
      separatedRows: true,
      items: [{ id: 'limited-free-models', component: 'custom', render: FreeModelsSettings }],
    },
    {
      id: 'model-manager',
      separatedRows: true,
      items: [{ id: 'model-manager', component: 'custom', render: ModelsSettings }],
    },
  ],
};
