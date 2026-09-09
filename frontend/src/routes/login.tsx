import React from "react";
import { useNavigate, useSearchParams, useLocation } from "react-router";
import { useIsAuthed } from "#/hooks/query/use-is-authed";
import { useConfig } from "#/hooks/query/use-config";
import { useGitHubAuthUrl } from "#/hooks/use-github-auth-url";
import { useEmailVerification } from "#/hooks/use-email-verification";
import { useInvitation } from "#/hooks/use-invitation";
import { LoginContent } from "#/components/features/auth/login-content";
import { EmailVerificationModal } from "#/components/features/waitlist/email-verification-modal";
import { RequestSubmittedModal } from "#/components/features/onboarding/request-submitted-modal";
import { navigateOrHardRedirect } from "#/utils/cross-app-redirect";
import { isLocalGatewayAdmin } from "#/utils/local-gateway-admin";
import { LocalGatewayLoginForm } from "#/components/features/auth/local-gateway-login-form";

interface LocationState {
  showRequestSubmittedModal?: boolean;
}

export function getSafeReturnTo(searchParams: URLSearchParams): string {
  const destination =
    searchParams.get("returnTo") || searchParams.get("redirect") || "/";
  if (!destination.startsWith("/") || destination.startsWith("//")) {
    return "/";
  }
  return destination;
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const returnTo = getSafeReturnTo(searchParams);
  const locationState = location.state as LocationState | null;

  const config = useConfig();
  const localAdmin = isLocalGatewayAdmin();
  const { data: isAuthed, isLoading: isAuthLoading } = useIsAuthed();
  const {
    emailVerified,
    hasDuplicatedEmail,
    recaptchaBlocked,
    wasRateLimited,
    emailVerificationModalOpen,
    setEmailVerificationModalOpen,
    userId,
  } = useEmailVerification();

  const { hasInvitation, buildOAuthStateData } = useInvitation();

  const gitHubAuthUrl = useGitHubAuthUrl({
    appMode: config.data?.app_mode || null,
    authUrl: config.data?.auth_url,
  });

  const [showRequestModal, setShowRequestModal] = React.useState(
    () => locationState?.showRequestSubmittedModal ?? false,
  );

  const handleRequestModalClose = () => {
    setShowRequestModal(false);
    navigate(location.pathname, { replace: true, state: {} });
  };

  // Redirect OSS mode users to home (local gateway admin still needs a login form)
  React.useEffect(() => {
    if (!config.isLoading && config.data?.app_mode === "oss" && !localAdmin) {
      navigate("/", { replace: true });
    }
  }, [config.isLoading, config.data?.app_mode, localAdmin, navigate]);

  // Redirect authenticated users away from login page
  // Preserve login_method param so useAuthCallback can store it for auto-login
  React.useEffect(() => {
    if (!isAuthLoading && isAuthed) {
      const loginMethod = searchParams.get("login_method");
      let destination = returnTo;
      if (localAdmin && (destination === "/" || destination === "")) {
        destination = "/settings/usage-monitoring";
      }
      if (loginMethod) {
        const separator = destination.includes("?") ? "&" : "?";
        destination = `${destination}${separator}login_method=${encodeURIComponent(loginMethod)}`;
      }
      navigateOrHardRedirect(navigate, destination, { replace: true });
    }
  }, [isAuthed, isAuthLoading, localAdmin, navigate, returnTo, searchParams]);

  if (isAuthLoading || config.isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-base">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white" />
      </div>
    );
  }

  // Don't render login content if user is authenticated or in OSS mode
  if (isAuthed || (config.data?.app_mode === "oss" && !localAdmin)) {
    return null;
  }

  if (localAdmin) {
    return (
      <main
        className="min-h-screen flex items-center justify-center bg-base p-4"
        data-testid="login-page"
      >
        <LocalGatewayLoginForm />
      </main>
    );
  }

  return (
    <>
      <main
        className="min-h-screen flex items-center justify-center bg-base p-4"
        data-testid="login-page"
      >
        <LoginContent
          githubAuthUrl={gitHubAuthUrl}
          appMode={config.data?.app_mode}
          authUrl={config.data?.auth_url}
          providersConfigured={config.data?.providers_configured}
          emailVerified={emailVerified}
          hasDuplicatedEmail={hasDuplicatedEmail}
          recaptchaBlocked={recaptchaBlocked}
          hasInvitation={hasInvitation}
          buildOAuthStateData={buildOAuthStateData}
        />
      </main>

      {emailVerificationModalOpen && (
        <EmailVerificationModal
          onClose={() => {
            setEmailVerificationModalOpen(false);
          }}
          userId={userId}
          wasRateLimited={wasRateLimited}
        />
      )}

      {showRequestModal && (
        <RequestSubmittedModal onClose={handleRequestModalClose} />
      )}
    </>
  );
}
