import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Select } from '../../../../components/ui';
import { SettingRow, SettingsSection } from '../../components';
import { useSettingsServices } from '../../services/SettingsServicesProvider';
import { SubscriptionSettings } from '../agent/ConversationSettings';
import { useCodexSubscription } from '../../../codexSubscription/state';
import './ResearchModelsSettings.css';

interface LocalModel {
  id: string;
  name: string;
  ready: boolean;
  reason: string;
}
interface Snapshot {
  selected_id: string;
  local_ready: boolean;
  local_models: LocalModel[];
  chatgpt_model: string | null;
  chatgpt_models: { id: string; name: string; default: boolean }[];
}

export function ResearchModelsSettings() {
  const { t } = useTranslation();
  const { request, isConnected, saveQueue, unsavedChanges } = useSettingsServices();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [mode, setMode] = useState('auto');
  const [chatgptModel, setChatgptModel] = useState('');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<'error' | 'saved' | null>(null);
  const subscriptionState = useCodexSubscription((state) => state.state);
  const initialized = useRef(false);
  const dirtyDraft = useRef(false);

  const apply = useCallback((value: Snapshot, preserveDraft = false) => {
    setSnapshot(value);
    if (!preserveDraft || !initialized.current || !dirtyDraft.current) {
      setMode(['auto', 'chatgpt_ai4r'].includes(value.selected_id) ? value.selected_id : 'codex');
      setChatgptModel(value.chatgpt_model ?? '');
    }
    initialized.current = true;
  }, []);
  const load = useCallback(async () => {
    if (!isConnected) return;
    setBusy(true);
    setFeedback(null);
    try {
      apply(await request<Snapshot>('research.models.get'), true);
    } catch {
      setFeedback('error');
    } finally {
      setBusy(false);
    }
  }, [apply, isConnected, request]);

  useEffect(() => {
    void load();
  }, [load, subscriptionState]);
  const dirty = Boolean(
    snapshot &&
      (mode !== snapshot.selected_id || (mode === 'codex' && chatgptModel !== (snapshot.chatgpt_model ?? ''))),
  );
  useEffect(() => {
    dirtyDraft.current = dirty;
    unsavedChanges.set('research-model-choice', dirty);
    return () => unsavedChanges.clear('research-model-choice');
  }, [dirty, unsavedChanges]);

  const save = async () => {
    setBusy(true);
    setFeedback(null);
    try {
      const value = await saveQueue.enqueue('research-model-choice', () =>
        request<Snapshot>('research.models.select', {
          preset_id: mode,
          ...(mode === 'codex' ? { chatgpt_model: chatgptModel || null } : {}),
        }),
      );
      apply(value);
      setFeedback('saved');
    } catch {
      setFeedback('error');
    } finally {
      setBusy(false);
    }
  };

  const disabled = busy || !isConnected || !snapshot;
  return (
    <>
      <SettingsSection title={t('researchModels.title')} description={t('researchModels.localDescription')} separatedRows>
        <div className="research-model-settings" data-testid="settings-research-models">
          <SettingRow title={t('researchModels.executionMode')} description={t('researchModels.localModeHint')}>
            <Select
              className="research-model-settings__control"
              value={mode}
              onChange={(value) => {
                setMode(value);
                setFeedback(null);
              }}
              disabled={disabled}
              options={[
                { value: 'auto', label: t('researchModels.localMode') },
                { value: 'chatgpt_ai4r', label: t('researchModels.ai4rReference') },
                { value: 'codex', label: t('researchModels.chatgptBaseline') },
              ]}
              aria-label={t('researchModels.executionMode')}
              data-testid="settings-research-model-mode"
            />
          </SettingRow>
          {(mode === 'auto' || mode === 'chatgpt_ai4r') && (
            <>
              {(snapshot?.local_models ?? []).filter((model) => ['gptoss20', 'lightning', 'gptoss'].includes(model.id)).map((model) => (
                <SettingRow
                  key={model.id}
                  title={model.name}
                  description={t(`researchModels.localRole.${model.id}`)}
                >
                  <span role="status" data-testid="settings-local-model-status" data-variant={model.id}>
                    {model.ready ? t('researchModels.localReady') : t(`researchModels.localStatus.${model.reason}`, {
                      defaultValue: t('researchModels.localUnavailable'),
                    })}
                  </span>
                </SettingRow>
              ))}
              {snapshot && !snapshot.local_ready && (
                <p className="research-model-settings__feedback" role="status" data-testid="settings-local-model-prerequisite">
                  {t('researchModels.localPrerequisite')}
                </p>
              )}
            </>
          )}
          {mode === 'codex' && (
            <SettingRow title={t('researchModels.chatgptModel')} description={t('researchModels.baselineHint')}>
              <Select
                className="research-model-settings__control"
                value={chatgptModel}
                onChange={setChatgptModel}
                disabled={disabled}
                options={[
                  { value: '', label: t('researchModels.codex') },
                  ...(snapshot?.chatgpt_models ?? []).map((model) => ({ value: model.id, label: model.name })),
                  ...(chatgptModel && !snapshot?.chatgpt_models.some((model) => model.id === chatgptModel)
                    ? [{ value: chatgptModel, label: chatgptModel }]
                    : []),
                ]}
                aria-label={t('researchModels.chatgptModel')}
                data-testid="settings-research-chatgpt-model"
              />
            </SettingRow>
          )}
          <SettingRow title={t('researchModels.applyMode')} description={t('researchModels.frozenPool')}>
            <Button
              onClick={() => void save()}
              loading={busy}
              disabled={disabled || !dirty}
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
          {feedback && (
            <p
              role="status"
              className="research-model-settings__feedback"
              data-testid="settings-research-model-status"
              data-variant={feedback}
            >
              {t(feedback === 'error' ? 'researchModels.localError' : 'researchModels.modeSaved')}
            </p>
          )}
        </div>
      </SettingsSection>
      <SubscriptionSettings showModelSelector={false} />
    </>
  );
}
