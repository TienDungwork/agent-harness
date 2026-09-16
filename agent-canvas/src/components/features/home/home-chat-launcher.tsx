import { useState } from "react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { CustomChatInput } from "#/components/features/chat/custom-chat-input";
import { useActiveBackend } from "#/contexts/active-backend-context";
import { useCreateConversation } from "#/hooks/mutation/use-create-conversation";
import { useLocalWorkspaces } from "#/hooks/query/use-local-workspaces";
import { useModelInterceptor } from "#/hooks/chat/use-model-interceptor";
import { useLlmConfigured } from "#/hooks/use-llm-configured";
import { HOME_PROMPT_DRAFT_KEY } from "#/hooks/chat/use-draft-persistence";
import { useChatAttachmentUpload } from "#/hooks/chat/use-chat-attachment-upload";
import { useConversationStore } from "#/stores/conversation-store";
import type { WorkspaceMode } from "#/api/conversation-metadata-store";
import { setPendingTaskAttachments } from "#/stores/pending-task-attachments-store";
import { enqueueHomeTaskPendingMessage } from "#/utils/enqueue-home-task-pending-message";
import { sendMessageWithAttachments } from "#/utils/send-message-with-attachments";
import AgentServerConversationService from "#/api/conversation-service/agent-server-conversation-service.api";
import {
  claimWarmLocalConversation,
  peekWarmLocalConversation,
} from "#/utils/warm-local-conversation";
import { useWarmLocalConversationActions } from "#/hooks/use-warm-local-conversation-prefetch";
import { useNavigation } from "#/context/navigation-context";
import { useIsCreatingConversation } from "#/hooks/use-is-creating-conversation";
import { Provider } from "#/types/settings";
import { Branch, GitRepository } from "#/types/git";
import { LocalWorkspace } from "#/types/workspace";
import { I18nKey } from "#/i18n/declaration";
import {
  displayErrorToast,
  TOAST_OPTIONS,
} from "#/utils/custom-toast-handlers";
import { getWorkspacesUnsupportedMessage } from "#/utils/workspaces-compatibility";
import type { PluginSpec } from "#/api/conversation-service/agent-server-conversation-service.types";
import { PluginPickerModal } from "#/components/features/plugins/plugin-picker-modal";
import { PluginPickerTrigger } from "#/components/features/plugins/plugin-picker-trigger";
import { HomeHeaderTitle } from "./home-header/home-header-title";
import { OpenLauncherButton } from "./open-launcher-button";
import { OpenWorkspaceDialog } from "./open-workspace-dialog";
import { OpenRepositoryDialog } from "./open-repository-dialog";
import { HomeGitControlBarPreview } from "./home-git-control-bar-preview";

export function HomeChatLauncher() {
  const { t } = useTranslation("Creanova");
  const { backend } = useActiveBackend();
  const { navigate } = useNavigation();
  const isLocal = backend.kind === "local";

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [pendingWorkspace, setPendingWorkspace] =
    useState<LocalWorkspace | null>(null);
  const [pendingRepository, setPendingRepository] =
    useState<GitRepository | null>(null);
  const [pendingBranch, setPendingBranch] = useState<Branch | null>(null);
  const [pendingProvider, setPendingProvider] = useState<Provider | null>(null);
  const [workspaceMode, setWorkspaceMode] =
    useState<WorkspaceMode>("local_repo");
  const [selectedPlugins, setSelectedPlugins] = useState<PluginSpec[]>([]);
  const [isPluginPickerOpen, setIsPluginPickerOpen] = useState(false);

  const { mutateAsync: createConversation, isPending } =
    useCreateConversation();
  const isCreatingElsewhere = useIsCreatingConversation();
  const isCreating = isPending || isCreatingElsewhere;
  const { isConfigured: isLlmConfigured, isLoading: isLlmConfigLoading } =
    useLlmConfigured();
  const llmBlocked = !isLlmConfigLoading && !isLlmConfigured;

  // Prefetch runs once in root-layout; Home only claims / rewarms.
  const { createWarm, rewarm } = useWarmLocalConversationActions();

  const { images, files, imagesMarkedUploadAsFile, clearAllFiles } =
    useConversationStore();
  const { handleUpload } = useChatAttachmentUpload();
  const { error: workspacesError } = useLocalWorkspaces({ enabled: isLocal });
  const workspacesUnsupportedMessage = isLocal
    ? getWorkspacesUnsupportedMessage(workspacesError, t)
    : null;

  const handleSubmit = (message: string) => {
    const trimmed = message.trim();
    const hasAttachments = images.length > 0 || files.length > 0;
    if ((!trimmed && !hasAttachments) || isCreating) return;
    if (llmBlocked) return;

    const attachmentSnapshot = {
      images: [...images],
      files: [...files],
    };

    // Local text: create empty (warm-pool) then sendMessage after navigate.
    // Gateway already attaches lean creanova_infra — VMS no longer blocks warm.
    const deferFirstMessage = isLocal && !hasAttachments && !!trimmed;
    let variables: Parameters<typeof createConversation>[0] = {
      query:
        hasAttachments || deferFirstMessage ? undefined : trimmed || undefined,
      entryPoint: "home_chat_launcher",
    };
    if (isLocal && pendingWorkspace) {
      variables = {
        ...variables,
        workingDir: pendingWorkspace.path,
        workspaceMode,
      };
    } else if (!isLocal && pendingRepository && pendingBranch) {
      variables = {
        ...variables,
        repository: {
          name: pendingRepository.full_name,
          gitProvider: pendingRepository.git_provider,
          branch: pendingBranch.name,
        },
      };
    }
    if (selectedPlugins.length > 0) {
      variables = { ...variables, plugins: selectedPlugins };
    }

    const canUseWarm =
      isLocal &&
      !pendingWorkspace &&
      selectedPlugins.length === 0 &&
      !variables.workingDir &&
      !variables.repository;

    // Skip the loading toast when a warm slot is already READY — Enter should
    // feel instant. Still toast when we must wait on create / warm in-flight.
    const warmReady = canUseWarm && peekWarmLocalConversation() !== null;
    const toastId = warmReady
      ? null
      : toast.loading(t(I18nKey.HOME$CREATING_CONVERSATION), TOAST_OPTIONS);

    void (async () => {
      try {
        let data = canUseWarm ? await claimWarmLocalConversation() : null;
        // Plain local text: never fall through to the heavy mutation (profiles
        // ensureQueryData + encrypted settings rebuild). Use the same direct
        // create path as warm-pool.
        if (!data && canUseWarm) {
          data = await createWarm();
        }
        if (!data) {
          data = await createConversation(variables);
        } else {
          rewarm();
        }
        if (toastId) toast.dismiss(toastId);
        try {
          sessionStorage.removeItem(HOME_PROMPT_DRAFT_KEY);
        } catch {
          // sessionStorage not available
        }
        const targetConversationId = data.conversation_id;
        const isTaskConversation = targetConversationId.startsWith("task-");

        if (hasAttachments) {
          const shouldDeferAttachments = !isLocal || isTaskConversation;

          if (shouldDeferAttachments) {
            const taskId =
              data.task_id ??
              (isTaskConversation
                ? targetConversationId.slice("task-".length)
                : null);

            if (!taskId) {
              displayErrorToast(null);
              return;
            }

            setPendingTaskAttachments(taskId, {
              content: trimmed,
              images: attachmentSnapshot.images,
              files: attachmentSnapshot.files,
              imagesMarkedUploadAsFile: [...imagesMarkedUploadAsFile],
            });
            clearAllFiles();
            await enqueueHomeTaskPendingMessage({
              conversationId: targetConversationId,
              text: trimmed,
              images: attachmentSnapshot.images,
              imagesMarkedUploadAsFile,
            });
            navigate(`/conversations/${targetConversationId}`);
            return;
          }
          try {
            await sendMessageWithAttachments({
              conversationId: targetConversationId,
              content: trimmed,
              images: attachmentSnapshot.images,
              files: attachmentSnapshot.files,
              imagesMarkedUploadAsFile,
              t,
            });
            clearAllFiles();
          } catch (error) {
            displayErrorToast(error instanceof Error ? error.message : null);
            return;
          }
        }

        if (deferFirstMessage && trimmed) {
          await enqueueHomeTaskPendingMessage({
            conversationId: targetConversationId,
            text: trimmed,
            images: [],
            imagesMarkedUploadAsFile: [],
          });
          navigate(`/conversations/${targetConversationId}`);
          void AgentServerConversationService.sendMessage(
            targetConversationId,
            {
              role: "user",
              content: [{ type: "text", text: trimmed }],
            },
          ).catch((error) => {
            displayErrorToast(error instanceof Error ? error.message : null);
          });
          return;
        }

        if (isTaskConversation && trimmed) {
          await enqueueHomeTaskPendingMessage({
            conversationId: targetConversationId,
            text: trimmed,
            images: [],
            imagesMarkedUploadAsFile: [],
          });
        }

        navigate(`/conversations/${targetConversationId}`);
      } catch (error) {
        if (toastId) toast.dismiss(toastId);
        displayErrorToast(error instanceof Error ? error.message : null);
      }
    })();
  };

  const handleSubmitWithModelGuard = useModelInterceptor(null, handleSubmit);

  return (
    <div
      data-testid="home-chat-launcher"
      className="flex w-full max-w-[800px] flex-col gap-4 md:px-4"
    >
      <div className="flex w-full justify-center">
        <HomeHeaderTitle />
      </div>

      <div className="rounded-xl bg-tertiary">
        {(pendingWorkspace ||
          (pendingRepository && pendingBranch && pendingProvider)) && (
          <HomeGitControlBarPreview
            pendingWorkspace={pendingWorkspace}
            pendingRepository={pendingRepository}
            pendingBranch={pendingBranch}
            pendingProvider={pendingProvider}
            backendKind={backend.kind}
            workspaceMode={isLocal ? workspaceMode : undefined}
            onWorkspaceModeChange={isLocal ? setWorkspaceMode : undefined}
            onClearWorkspace={() => setPendingWorkspace(null)}
            onClearRepository={() => {
              setPendingRepository(null);
              setPendingBranch(null);
              setPendingProvider(null);
            }}
          />
        )}
        <CustomChatInput
          disabled={llmBlocked}
          isDisabled={isCreating || llmBlocked}
          onSubmit={handleSubmitWithModelGuard}
          draftStorageKey={HOME_PROMPT_DRAFT_KEY}
          onUpload={handleUpload}
          startButtons={
            <>
              <OpenLauncherButton
                kind={isLocal ? "local" : "cloud"}
                onClick={() => setIsDialogOpen(true)}
                disabled={Boolean(workspacesUnsupportedMessage)}
                disabledTooltip={workspacesUnsupportedMessage}
              />
              {isLocal ? (
                <PluginPickerTrigger
                  count={selectedPlugins.length}
                  onClick={() => setIsPluginPickerOpen(true)}
                />
              ) : null}
            </>
          }
        />
      </div>

      {isLocal ? (
        <OpenWorkspaceDialog
          isOpen={isDialogOpen}
          onOpenChange={setIsDialogOpen}
          onConfirm={(workspace) => {
            setPendingWorkspace(workspace);
            setPendingRepository(null);
            setPendingBranch(null);
            setPendingProvider(null);
            setIsDialogOpen(false);
          }}
        />
      ) : (
        <OpenRepositoryDialog
          isOpen={isDialogOpen}
          onOpenChange={setIsDialogOpen}
          onConfirm={({ repository, branch, provider }) => {
            setPendingRepository(repository);
            setPendingBranch(branch);
            setPendingProvider(provider);
            setPendingWorkspace(null);
            setIsDialogOpen(false);
          }}
        />
      )}

      {isLocal && isPluginPickerOpen ? (
        <PluginPickerModal
          onClose={() => setIsPluginPickerOpen(false)}
          selected={selectedPlugins}
          onChange={setSelectedPlugins}
        />
      ) : null}
    </div>
  );
}
