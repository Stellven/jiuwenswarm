import modelPresets from '../../../../../../../../research_contracts/model-presets/catalog.json';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Input, Select } from '../../../../components/ui';
import { hasResearchSession } from '../../../../utils/researchClient';
import { SettingRow, SettingsSection } from '../../components';
import { useSettingsServices } from '../../services/SettingsServicesProvider';
import { SubscriptionSettings } from '../agent/ConversationSettings';
import { useCodexSubscription } from '../../../codexSubscription/state';
import './ResearchModelsSettings.css';

interface Choice {
  id: string;
  name: string;
  model_name: string;
  base_url: string;
  platform_id: string;
  platform_name: string;
  configured: boolean;
  requires_api_key?: boolean;
}
interface Snapshot {
  selected_id: string;
  choices: Choice[];
  api_ready: boolean;
  chatgpt_model: string | null;
  chatgpt_models: { id: string; name: string; default: boolean }[];
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
  const subscriptionState = useCodexSubscription((state) => state.state);
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
  const isChatGPT = choiceId === 'codex' || choiceId.startsWith('codex:');
  const requiresApiKey = !isChatGPT && choice?.requires_api_key !== false;
  const selectedId =
    snapshot?.selected_id === 'codex' && snapshot.chatgpt_model
      ? `codex:${snapshot.chatgpt_model}`
      : snapshot?.selected_id;
  const dirty = Boolean(snapshot && (choiceId !== selectedId || apiKey));

  const apply = useCallback((value: Snapshot) => {
    setSnapshot(value);
    setChoiceId(
      value.selected_id === 'codex' && value.chatgpt_model ? `codex:${value.chatgpt_model}` : value.selected_id,
    );
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
  }, [load, subscriptionState]);
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
        isChatGPT
          ? request<Snapshot>('research.models.select', {
              preset_id: 'codex',
              chatgpt_model: choiceId.startsWith('codex:') ? choiceId.slice(6) : null,
            })
          : requiresApiKey
            ? request<Snapshot>('research.models.save', {
                preset_id: choiceId,
                api_key: apiKey,
              })
            : request<Snapshot>('research.models.select', { preset_id: choiceId }),
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
    snapshot?.selected_id === 'codex'
      ? (snapshot.chatgpt_models?.find((item) => item.id === snapshot.chatgpt_model)?.name ??
        snapshot.chatgpt_model ??
        t('researchModels.codex'))
      : (snapshot?.choices.find((item) => item.id === snapshot.selected_id)?.name ?? t('researchModels.codex'));
  return (
    <>
      <SettingsSection title={t('researchModels.title')} description={t('researchModels.description')} separatedRows>
        <div className="research-model-settings" data-testid="settings-research-models">
          {!enabled && (
            <SettingRow title={t('researchModels.title')} description={t('researchModels.authenticationRequired')} />
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
                ...(snapshot?.chatgpt_models ?? []).map((item) => ({
                  value: `codex:${item.id}`,
                  label: t('researchModels.chatgptOption', { model: item.name }),
                })),
                ...(snapshot?.chatgpt_model &&
                !snapshot.chatgpt_models?.some((item) => item.id === snapshot.chatgpt_model)
                  ? [
                      {
                        value: `codex:${snapshot.chatgpt_model}`,
                        label: t('researchModels.chatgptOption', { model: snapshot.chatgpt_model }),
                      },
                    ]
                  : []),
                ...choices.map((item) => ({
                  value: item.id,
                  label: t(item.requires_api_key === false ? 'researchModels.localOption' : 'researchModels.option', {
                    model: item.name,
                    platform: item.platform_name,
                  }),
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
          {!isChatGPT && !requiresApiKey && (
            <SettingRow
              title={t('researchModels.localEndpoint')}
              description={t('researchModels.localManaged', { model: choice?.model_name })}
            />
          )}
          {requiresApiKey && (
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
              disabled={disabled || !dirty || (requiresApiKey && !apiKey.trim() && !choice?.configured)}
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
              {t(
                error
                  ? isChatGPT
                    ? 'researchModels.chatgptError'
                    : requiresApiKey
                      ? 'researchModels.error'
                      : 'researchModels.localError'
                  : 'researchModels.saved',
              )}
            </p>
          )}
        </div>
      </SettingsSection>
      {isChatGPT && <SubscriptionSettings showModelSelector={false} />}
    </>
  );
}
