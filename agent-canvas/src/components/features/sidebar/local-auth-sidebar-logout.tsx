import { Link, useNavigate } from "react-router";
import { isLocalAuthEnabled } from "#/api/local-auth/client";
import { useLocalAuthUser, useLocalLogout } from "#/api/local-auth/hooks";
import { BrandButton } from "#/components/features/settings/brand-button";

export function LocalAuthSidebarLogout() {
  const enabled = isLocalAuthEnabled();
  const { data: user } = useLocalAuthUser();
  const logout = useLocalLogout();
  const navigate = useNavigate();

  if (!enabled || !user) return null;

  return (
    <div className="flex flex-col gap-1.5 pb-1">
      <p
        className="truncate px-1 text-xs text-neutral-400"
        data-testid="local-auth-username"
        title={user.username}
      >
        {user.username}
        {typeof user.credit_balance === "number"
          ? ` · ${user.credit_balance.toFixed(0)} credits`
          : ""}
      </p>
      {user.is_admin ? (
        <Link
          to="/admin/users"
          className="px-1 text-xs text-neutral-400 hover:text-white"
          data-testid="local-admin-link"
        >
          Admin · users
        </Link>
      ) : null}
      <BrandButton
        type="button"
        variant="secondary"
        testId="local-auth-logout"
        className="w-full"
        isDisabled={logout.isPending}
        onClick={async () => {
          await logout.mutateAsync();
          navigate("/login", { replace: true });
        }}
      >
        {logout.isPending ? "Signing out…" : "Sign out"}
      </BrandButton>
    </div>
  );
}
