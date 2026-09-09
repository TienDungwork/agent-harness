import { useTranslation } from "react-i18next";
import CreanovaLogo from "#/assets/branding/Creanova-logo.svg?react";
import CreanovaLogoFull from "#/assets/branding/Creanova-logo-full.svg?react";
import { NavigationLink } from "#/components/shared/navigation-link";
import { I18nKey } from "#/i18n/declaration";
import { cn } from "#/utils/utils";

/** Mark-only C glyph (~227×190). */
const DEFAULT_MARK_WIDTH = 40;
const DEFAULT_MARK_HEIGHT = Math.round((DEFAULT_MARK_WIDTH * 190) / 227);

/** Full wordmark + tagline (~953×221). */
const DEFAULT_FULL_WIDTH = 220;
const DEFAULT_FULL_HEIGHT = Math.round((DEFAULT_FULL_WIDTH * 221) / 953);

export type CreanovaLogoButtonProps = {
  className?: string;
  /** Applied to the root `<svg>` (e.g. `max-w-none` so Tailwind preflight doesn’t clamp wide marks inside a narrow flex slot). */
  logoClassName?: string;
  logoWidth?: number;
  logoHeight?: number;
  /** `mark` = icon only; `full` = CREANOVA wordmark + tagline. */
  variant?: "mark" | "full";
};

export function CreanovaLogoButton({
  className,
  logoClassName,
  logoWidth,
  logoHeight,
  variant = "mark",
}: CreanovaLogoButtonProps = {}) {
  const { t } = useTranslation("Creanova");
  const ariaLabel = t(I18nKey.BRANDING$Creanova_LOGO);

  const width =
    logoWidth ?? (variant === "full" ? DEFAULT_FULL_WIDTH : DEFAULT_MARK_WIDTH);
  const height =
    logoHeight ??
    (variant === "full" ? DEFAULT_FULL_HEIGHT : DEFAULT_MARK_HEIGHT);

  const Logo = variant === "full" ? CreanovaLogoFull : CreanovaLogo;

  return (
    <NavigationLink
      to="/conversations"
      aria-label={ariaLabel}
      className={cn(className)}
    >
      <Logo
        width={width}
        height={height}
        className={cn("shrink-0", logoClassName)}
      />
    </NavigationLink>
  );
}
