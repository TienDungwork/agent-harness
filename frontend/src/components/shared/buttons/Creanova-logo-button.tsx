import { NavLink } from "react-router";
import { useTranslation } from "react-i18next";
import CreanovaLogo from "#/assets/branding/Creanova-logo.svg?react";
import { I18nKey } from "#/i18n/declaration";
import { StyledTooltip } from "#/components/shared/buttons/styled-tooltip";

export function CreanovaLogoButton() {
  const { t } = useTranslation();

  const tooltipText = t(I18nKey.BRANDING$Creanova);
  const ariaLabel = t(I18nKey.BRANDING$Creanova_LOGO);

  return (
    <StyledTooltip content={tooltipText}>
      <NavLink to="/" aria-label={ariaLabel}>
        <CreanovaLogo width={46} height={30} />
      </NavLink>
    </StyledTooltip>
  );
}
