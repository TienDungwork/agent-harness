import { useTranslation } from "react-i18next";
import { BaseModalTitle } from "#/components/shared/modals/confirmation-modals/base-modal";
import { ModalCloseButton } from "#/components/shared/modals/modal-close-button";
import { Typography } from "#/ui/typography";
import { I18nKey } from "#/i18n/declaration";

interface SystemMessageHeaderProps {
  agentClass: string | null;
  CreanovaVersion: string | null;
  onClose: () => void;
}

export function SystemMessageHeader({
  agentClass,
  CreanovaVersion,
  onClose,
}: SystemMessageHeaderProps) {
  const { t } = useTranslation("Creanova");

  return (
    <>
      <ModalCloseButton onClose={onClose} testId="close-system-message-modal" />
      <div className="flex w-full min-w-0 flex-col gap-2 pr-6">
        <BaseModalTitle title={t(I18nKey.SYSTEM_MESSAGE_MODAL$TITLE)} />
        {(agentClass || CreanovaVersion) && (
          <div className="flex flex-col gap-2">
            {agentClass && (
              <div className="text-sm">
                <Typography.Text className="font-semibold text-[var(--oh-text-tertiary)]">
                  {t(I18nKey.SYSTEM_MESSAGE_MODAL$AGENT_CLASS)}
                </Typography.Text>{" "}
                <Typography.Text className="font-medium text-content-2">
                  {agentClass}
                </Typography.Text>
              </div>
            )}
            {CreanovaVersion && (
              <div className="text-sm">
                <Typography.Text className="font-semibold text-[var(--oh-text-tertiary)]">
                  {t(I18nKey.SYSTEM_MESSAGE_MODAL$Creanova_VERSION)}
                </Typography.Text>{" "}
                <Typography.Text className="text-content-2">
                  {CreanovaVersion}
                </Typography.Text>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
