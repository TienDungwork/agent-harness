import React from "react";
import { Navigate, useNavigate } from "react-router";
import { BrandButton } from "#/components/features/settings/brand-button";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import { isLocalAuthEnabled } from "#/api/local-auth/client";
import {
  useLocalAuthUser,
  useLocalLogin,
} from "#/api/local-auth/hooks";
import { useIsAuthed } from "#/hooks/query/use-is-authed";

export default function LocalLoginScreen() {
  const navigate = useNavigate();
  const enabled = isLocalAuthEnabled();
  const { data: isAuthed, isLoading: authLoading } = useIsAuthed();
  const { refetch } = useLocalAuthUser();
  const login = useLocalLogin();

  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  if (!enabled) {
    return <Navigate to="/" replace />;
  }

  if (authLoading) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-base">
        <LoadingSpinner size="large" />
      </main>
    );
  }

  if (isAuthed) {
    return <Navigate to="/" replace />;
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await login.mutateAsync({ username, password });
      await refetch();
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <main
      data-testid="local-login-screen"
      className="min-h-screen flex items-center justify-center bg-base px-4"
    >
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md rounded-2xl border border-white/10 bg-base/90 p-8 shadow-2xl space-y-5"
      >
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold text-white">Creanova</h1>
          <p className="text-sm text-neutral-400">
            Đăng nhập bằng tài khoản do admin cấp (mặc định: demo / demo123)
          </p>
        </div>

        <label className="block space-y-1.5">
          <span className="text-sm text-neutral-300">Username</span>
          <input
            data-testid="local-login-username"
            className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-white outline-none focus:border-white/30"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>

        <label className="block space-y-1.5">
          <span className="text-sm text-neutral-300">Password</span>
          <input
            data-testid="local-login-password"
            type="password"
            className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-white outline-none focus:border-white/30"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        {error ? (
          <p
            data-testid="local-login-error"
            className="text-sm text-red-400 break-words"
          >
            {error}
          </p>
        ) : null}

        <BrandButton
          type="submit"
          variant="primary"
          testId="local-login-submit"
          isDisabled={login.isPending || !username || !password}
          className="w-full"
        >
          {login.isPending ? "Signing in…" : "Sign in"}
        </BrandButton>
      </form>
    </main>
  );
}
