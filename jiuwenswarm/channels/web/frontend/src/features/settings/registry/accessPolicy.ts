import type { SettingsAccessPolicy } from './types';
import { useCodexSubscription } from '../../codexSubscription/state';

export const openSourceSettingsAccessPolicy: SettingsAccessPolicy = {
  evaluate(node) {
    if (node.kind === 'section' && node.moduleId === 'models' &&
        ['limited-free-models', 'model-manager'].includes(node.sectionId) &&
        useCodexSubscription.getState().enabled) return { level: 'hidden' };
    if (node.kind === 'section' && node.moduleId === 'experimental' && node.sectionId === 'kv-cache-affinity') {
      return { level: 'hidden' };
    }
    return { level: 'editable' };
  },
};
