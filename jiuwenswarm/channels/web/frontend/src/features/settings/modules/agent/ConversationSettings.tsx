import { useTranslation } from 'react-i18next';
import { SettingRow } from '../../components/SettingRow';
import { useSettingsServices } from '../../services/SettingsServicesProvider';
import { CodexSubscriptionPanel } from '../../../codexSubscription/CodexSubscriptionPanel';
import { useCodexSubscription } from '../../../codexSubscription/state';
import { hasLocalChat } from '../../../../utils/researchClient';
import { Select } from '../../../../components/ui/Select/Select';

export function SubscriptionSettings({ showModelSelector = true }: { showModelSelector?: boolean } = {}) {
  const { isConnected, request } = useSettingsServices();
  const enabled = useCodexSubscription((state) => state.enabled);
  return enabled ? (
    <CodexSubscriptionPanel connected={isConnected} request={request} showModelSelector={showModelSelector} />
  ) : null;
}

export function ConversationCapsuleSettings({ disabled }: { disabled: boolean }) {
  const { t } = useTranslation();
  const capsule = useCodexSubscription((state) => state.capsule);
  if (!hasLocalChat()) return null;
  return (
    <SettingRow title={t('codexSubscription.capsuleTitle')} description={t('codexSubscription.capsuleDescription')}>
      <Select
        data-testid="settings-conversation-capsule"
        aria-label={t('codexSubscription.capsuleTitle')}
        value={capsule}
        disabled={disabled}
        options={[
          { value: '', label: t('codexSubscription.capsuleGeneral') },
          { value: 'document-analyst', label: t('codexSubscription.capsuleDocument') },
          { value: 'research-brief', label: t('codexSubscription.capsuleBrief') },
        ]}
        onChange={(value) => useCodexSubscription.getState().set({ capsule: value })}
      />
    </SettingRow>
  );
}
