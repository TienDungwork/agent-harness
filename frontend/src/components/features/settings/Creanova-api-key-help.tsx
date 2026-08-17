import { useTranslation } from "react-i18next";
import { HelpLink } from "#/ui/help-link";
import { I18nKey } from "#/i18n/declaration";
import { Typography } from "#/ui/typography";

interface CreanovaApiKeyHelpProps {
  testId: string;
}

export function CreanovaApiKeyHelp({ testId }: CreanovaApiKeyHelpProps) {
  const { t } = useTranslation();

  return (
    <>
      <HelpLink
        testId={testId}
        text={t(I18nKey.SETTINGS$Creanova_API_KEY_HELP_TEXT)}
        linkText={t(I18nKey.SETTINGS$NAV_API_KEYS)}
        href="https://app.all-hands.dev/settings/api-keys"
        suffix={` ${t(I18nKey.SETTINGS$Creanova_API_KEY_HELP_SUFFIX)}`}
      />
      <Typography.Paragraph className="text-xs">
        {t(I18nKey.SETTINGS$LLM_BILLING_INFO)}{" "}
        <a
          href="https://docs.Creanova.dev/usage/llms/Creanova-llms"
          rel="noreferrer noopener"
          target="_blank"
          className="underline underline-offset-2"
        >
          {t(I18nKey.SETTINGS$SEE_PRICING_DETAILS)}
        </a>
      </Typography.Paragraph>
    </>
  );
}
