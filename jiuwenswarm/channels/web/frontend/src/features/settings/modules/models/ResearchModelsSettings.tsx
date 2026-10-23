import modelPresets from '../../../../../../../../research_contracts/model-presets/catalog.json';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Input, Select } from '../../../../components/ui';
import { hasResearchSession } from '../../../../utils/researchClient';
import { SettingRow, SettingsSection } from '../../components';
import { useSettingsServices } from '../../services/SettingsServicesProvider';
import { SubscriptionSettings } from '../agent/ConversationSettings';
import './ResearchModelsSettings.css';

interface Choice {
  id: string;
  name: string;
  model_name: string;
  base_url: string;
  platform_id: string;
  platform_name: string;
  configured: boolean;
}
interface Snapshot {
  selected_id: string;
  choices: Choice[];
  api_ready: boolean;
}

export function ResearchModelsSettings() {
  const { t } = useTranslation();
  const { request, isConnected, saveQueue, unsavedChanges } = useSettingsServices();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [choiceId, setChoiceId] = useState('codex');
  const [apiKey, setApiKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [saved, setSaved] = useState(false);
  const [enabled, setEnabled] = useState(hasResearchSession);
  useEffect(() => {
    const update = () => setEnabled(hasResearchSession());
    window.addEventListener('research.runtime.changed', update);
    window.addEventListener('focus', update);
    return () => {
      window.removeEventListener('research.runtime.changed', update);
      window.removeEventListener('focus', update);
    };
  }, []);
  const choices: Choice[] = snapshot?.choices ?? modelPresets.map((item) => ({ ...item, configured: false }));
  const choice = choices.find((item) => item.id === choiceId);
  const dirty = Boolean(snapshot && (choiceId !== snapshot.selected_id || apiKey));

  const apply = useCallback((value: Snapshot) => {
    setSnapshot(value);
    setChoiceId(value.selected_id);
    setApiKey('');
  }, []);

  const load = useCallback(async () => {
    if (!isConnected) return;
    setBusy(true);
    setError(false);
    try {
      apply(await request<Snapshot>('research.models.get'));
      setEnabled(true);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }, [apply, isConnected, request]);

  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    unsavedChanges.set('research-model-choice', dirty);
    return () => unsavedChanges.clear('research-model-choice');
  }, [dirty, unsavedChanges]);

  const save = async () => {
    setBusy(true);
    setError(false);
    setSaved(false);
    try {
      const value = await saveQueue.enqueue('research-model-choice', () =>
        choiceId === 'codex'
          ? request<Snapshot>('research.models.select', { preset_id: 'codex' })
          : request<Snapshot>('research.models.save', {
              preset_id: choiceId,
              api_key: apiKey,
            }),
      );
      apply(value);
      setSaved(true);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  const disabled = busy || !isConnected || !snapshot;
  const currentName =
    snapshot?.choices.find((item) => item.id === snapshot.selected_id)?.name ?? t('researchModels.codex');
  return (
    <>
      <SettingsSection title={t('researchModels.title')} description={t('researchModels.description')} separatedRows>
        <div className="research-model-settings" data-testid="settings-research-models">
          {!enabled && (
            <SettingRow title={t('researchModels.apiKey')} description={t('researchModels.authenticationRequired')} />
          )}
          <SettingRow
            title={t('researchModels.model')}
            description={t('researchModels.current', { model: currentName })}
          >
            <Select
              className="research-model-settings__control"
              value={choiceId}
              disabled={busy || !isConnected}
              options={[
                { value: 'codex', label: t('researchModels.codex') },
                ...choices.map((item) => ({
                  value: item.id,
                  label: t('researchModels.option', { model: item.name, platform: item.platform_name }),
                })),
              ]}
              onChange={(id) => {
                setChoiceId(id);
                setApiKey('');
                setSaved(false);
              }}
              aria-label={t('researchModels.model')}
              data-testid="settings-research-model-select"
            />
          </SettingRow>
          {choiceId !== 'codex' && (
            <>
              <SettingRow
                title={t('researchModels.platformKey', { platform: choice?.platform_name ?? 'OpenRouter' })}
                description={t('researchModels.keyPrivacy')}
              >
                <Input
                  className="research-model-settings__control"
                  type="password"
                  value={apiKey}
                  onChange={setApiKey}
                  changeOnBlur={false}
                  disabled={disabled}
                  autoComplete="new-password"
                  placeholder={t(choice?.configured ? 'researchModels.keySaved' : 'researchModels.keyPlaceholder')}
                  passwordVisibilityLabels={{ show: t('researchModels.showKey'), hide: t('researchModels.hideKey') }}
                  aria-label={t('researchModels.apiKey')}
                  data-testid="settings-research-model-api-key"
                />
              </SettingRow>
            </>
          )}
          <SettingRow title={t('researchModels.apply')} description={t('researchModels.newRuns')}>
            <Button
              onClick={() => void save()}
              loading={busy}
              disabled={disabled || !dirty || (choiceId !== 'codex' && !apiKey.trim() && !choice?.configured)}
              variant="primary"
              data-testid="settings-research-model-save"
            >
              {t('researchModels.saveUse')}
            </Button>
            <Button
              onClick={() => void load()}
              disabled={busy || !isConnected}
              data-testid="settings-research-model-refresh"
            >
              {t('researchModels.refresh')}
            </Button>
          </SettingRow>
          {(error || saved) && (
            <p
              role="status"
              className="research-model-settings__feedback"
              data-testid="settings-research-model-status"
              data-variant={error ? 'error' : 'saved'}
            >
              {t(error ? 'researchModels.error' : 'researchModels.saved')}
            </p>
          )}
        </div>
      </SettingsSection>
      {choiceId === 'codex' && <SubscriptionSettings showModelSelector={false} />}
    </>
  );
}
