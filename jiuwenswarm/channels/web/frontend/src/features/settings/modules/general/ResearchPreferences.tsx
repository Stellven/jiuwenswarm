import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Input, Select, Switch } from '../../../../components/ui';
import { SettingRow } from '../../components';
import { useSettingsServices } from '../../services/SettingsServicesProvider';
import { hasResearchSession } from '../../../../utils/researchClient';

type Values = Record<string, string | string[] | boolean>;
type Scope = 'account' | 'host' | 'project';
interface PreferenceSnapshot {
  scopes: Record<Scope, Values>;
  effective: Values;
  applies_on: 'next_start';
}
const TEXT_FIELDS = [
  'display_name',
  'timezone',
  'runtime_choice',
  'workspace_input',
  'workspace_poc',
  'knowledge_paths',
  'search_options',
  'reasoning_options',
  'ui_behavior',
  'ingestion_extensions',
];
const ARRAY_FIELDS = new Set(['knowledge_paths', 'ingestion_extensions']);

export function ResearchPreferences({ disabled = false }: { disabled?: boolean }) {
  const { t } = useTranslation();
  const { request, saveQueue, unsavedChanges } = useSettingsServices();
  const [snapshot, setSnapshot] = useState<PreferenceSnapshot | null>(null);
  const [scope, setScope] = useState<Scope>('account');
  const [draft, setDraft] = useState<Values>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const enabled = hasResearchSession();
  const dirty = snapshot !== null && JSON.stringify(draft) !== JSON.stringify(snapshot.scopes[scope]);

  useEffect(() => {
    if (!enabled) return;
    let live = true;
    void request<PreferenceSnapshot>('research.preferences.get')
      .then((value) => {
        if (live) {
          setSnapshot(value);
          setDraft(value.scopes.account);
        }
      })
      .catch(() => {
        if (live) setError(true);
      });
    return () => {
      live = false;
    };
  }, [enabled, request]);
  useEffect(() => {
    unsavedChanges.set('research-preferences', dirty);
    return () => unsavedChanges.clear('research-preferences');
  }, [dirty, unsavedChanges]);
  if (!enabled) return null;
  const save = () => {
    setBusy(true);
    setError(false);
    const values = Object.fromEntries(
      Object.entries(draft).filter(([, value]) => value !== '' && (!Array.isArray(value) || value.length > 0)),
    );
    void saveQueue
      .enqueue(
        'research.preferences.save',
        () => request<PreferenceSnapshot>('research.preferences.save', { scope, values }),
        { errorScope: 'caller' },
      )
      .then((value) => {
        setSnapshot(value);
        setDraft(value.scopes[scope]);
      })
      .catch(() => setError(true))
      .finally(() => setBusy(false));
  };
  return (
    <>
      <SettingRow title={t('researchPreferences.title')} description={t('researchPreferences.nextStart')}>
        <Select
          value={scope}
          disabled={disabled || busy || dirty || !snapshot}
          options={(['account', 'host', 'project'] as Scope[]).map((value) => ({
            value,
            label: t(`researchPreferences.scope.${value}`),
          }))}
          onChange={(value) => {
            const next = value as Scope;
            setScope(next);
            setDraft(snapshot?.scopes[next] ?? {});
          }}
          aria-label={t('researchPreferences.scopeLabel')}
          data-testid="settings-research-preference-scope"
        />
      </SettingRow>
      {TEXT_FIELDS.map((field) => (
        <SettingRow key={field} title={t(`researchPreferences.fields.${field}`)}>
          <Input
            value={Array.isArray(draft[field]) ? (draft[field] as string[]).join(', ') : String(draft[field] ?? '')}
            disabled={disabled || busy || !snapshot}
            aria-label={t(`researchPreferences.fields.${field}`)}
            onChange={(value) =>
              setDraft((current) => ({
                ...current,
                [field]: ARRAY_FIELDS.has(field)
                  ? value
                      .split(',')
                      .map((entry) => entry.trim())
                      .filter(Boolean)
                  : value,
              }))
            }
            data-testid="settings-research-preference-input"
            data-variant={field}
          />
        </SettingRow>
      ))}
      <SettingRow title={t('researchPreferences.fields.single_gpu')}>
        <Switch
          checked={draft.single_gpu === true}
          disabled={disabled || busy || !snapshot}
          onChange={(value) => setDraft((current) => ({ ...current, single_gpu: value }))}
          aria-label={t('researchPreferences.fields.single_gpu')}
          data-testid="settings-research-preference-single-gpu"
        />
      </SettingRow>
      <SettingRow
        title={t('researchPreferences.saveTitle')}
        description={error ? t('researchShell.operationFailed') : undefined}
      >
        <Button
          disabled={disabled || busy || !dirty}
          onClick={() => setDraft(snapshot?.scopes[scope] ?? {})}
          data-testid="settings-research-preference-discard-btn"
        >
          {t('researchPreferences.discard')}
        </Button>
        <Button
          disabled={disabled || busy || !dirty}
          onClick={save}
          data-testid="settings-research-preference-save-btn"
        >
          {t('researchPreferences.save')}
        </Button>
      </SettingRow>
    </>
  );
}
