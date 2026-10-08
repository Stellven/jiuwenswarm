import { requestSettingsModule } from '../../features/settings/settingsNavigation';
import { useChatStore } from '../../stores/chatStore';
import { resolveChatModelSelection, useSessionStore } from '../../stores/sessionStore';
import ModelPicker from '../ModelPicker';
import { useCodexSubscription } from '../../features/codexSubscription/state';

function openModelSettings(): void {
  requestSettingsModule('models');
}

export default function ChatModelSelector({ disabled = false }: { disabled?: boolean }): JSX.Element | null {
  const models = useSessionStore((state) => state.chatAvailableModels);
  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const selectedModelName = useSessionStore(
    (state) => state.runtimes[activeSessionId ?? '']?.selectedModelName ?? null,
  );
  const defaultModelName = useSessionStore((state) => state.defaultModelName);
  const setSelectedModelName = useSessionStore((state) => state.setSelectedModelName);
  const subscriptionMode = useCodexSubscription((state) => state.enabled);
  // Preserve the chat.send model resolution; the shared picker does not choose defaults.
  const selected = resolveChatModelSelection(models, selectedModelName, defaultModelName);
  if (subscriptionMode || !selected) return null;

  return (
    <ModelPicker
      testIdPrefix="chat-panel-model-selector"
      value={selected.model_name}
      onChange={(modelName) => {
        if (activeSessionId) setSelectedModelName(activeSessionId, modelName);
      }}
      disabled={disabled}
      onAddModel={openModelSettings}
    />
  );
}
