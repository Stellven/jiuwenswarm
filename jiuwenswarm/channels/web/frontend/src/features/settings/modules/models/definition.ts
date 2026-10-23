import { settingsNavigationIcons } from '../../../../assets/settings';
import type { SettingsModuleDefinition } from '../../registry/types';
import { ResearchModelsSettings } from './ResearchModelsSettings';

export const modelsModule: SettingsModuleDefinition = {
  id: 'models',
  titleKey: 'settingsPanel.categories.models',
  icon: settingsNavigationIcons.models,
  source: 'config',
  sections: [
    {
      id: 'research-model-choice',
      separatedRows: true,
      items: [{ id: 'research-model-choice', component: 'custom', render: ResearchModelsSettings }],
    },
  ],
};
