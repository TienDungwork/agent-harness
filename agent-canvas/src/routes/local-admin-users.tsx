import React from "react";
import { Navigate } from "react-router";
import { BrandButton } from "#/components/features/settings/brand-button";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import {
  createAdminUser,
  fetchAdminUsers,
  isLocalAuthEnabled,
  setAdminUserActive,
  setAdminUserCredits,
  type AdminUserSummary,
} from "#/api/local-auth/client";
import { useLocalAuthUser } from "#/api/local-auth/hooks";

export default function LocalAdminUsersScreen() {
  const enabled = isLocalAuthEnabled();
  const { data: me, isLoading: meLoading } = useLocalAuthUser();
  const [users, setUsers] = React.useState<AdminUserSummary[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [busyId, setBusyId] = React.useState<string | null>(null);
  const [drafts, setDrafts] = React.useState<Record<string, string>>({});
  const [newUsername, setNewUsername] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [newCredits, setNewCredits] = React.useState("100");

  const reload = React.useCallback(async () => {
    setError(null);
    try {
      setUsers(await fetchAdminUsers());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  React.useEffect(() => {
    if (me?.is_admin) void reload();
  }, [me?.is_admin, reload]);

  if (!enabled) return <Navigate to="/" replace />;
  if (meLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoadingSpinner size="large" />
      </div>
    );
  }
  if (!me?.is_admin) {
    return (
      <div className="p-6 text-red-400" data-testid="admin-forbidden">
        Admin only
      </div>
    );
  }

  return (
    <div
      className="mx-auto max-w-4xl space-y-4 p-6"
      data-testid="local-admin-users"
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-white">Users & credits</h1>
          <p className="text-sm text-neutral-400">
            Tạo user (local backend) và quản lý credits. Không cần Docker.
          </p>
        </div>
        <BrandButton
          type="button"
          variant="secondary"
          testId="admin-refresh"
          onClick={() => void reload()}
        >
          Refresh
        </BrandButton>
      </div>

      <form
        className="flex flex-wrap items-end gap-2 rounded-xl border border-white/10 p-3"
        data-testid="admin-create-user"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusyId("create");
          setError(null);
          try {
            await createAdminUser({
              username: newUsername.trim(),
              password: newPassword,
              initial_credits: Number(newCredits) || 100,
            });
            setNewUsername("");
            setNewPassword("");
            await reload();
          } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
          } finally {
            setBusyId(null);
          }
        }}
      >
        <label className="space-y-1 text-xs text-neutral-400">
          Username
          <input
            className="block w-40 rounded border border-white/10 bg-black/30 px-2 py-1 text-sm text-white"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
            required
            data-testid="admin-new-username"
          />
        </label>
        <label className="space-y-1 text-xs text-neutral-400">
          Password
          <input
            type="password"
            className="block w-40 rounded border border-white/10 bg-black/30 px-2 py-1 text-sm text-white"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            data-testid="admin-new-password"
          />
        </label>
        <label className="space-y-1 text-xs text-neutral-400">
          Credits
          <input
            className="block w-24 rounded border border-white/10 bg-black/30 px-2 py-1 text-sm text-white"
            value={newCredits}
            onChange={(e) => setNewCredits(e.target.value)}
            data-testid="admin-new-credits"
          />
        </label>
        <BrandButton
          type="submit"
          variant="primary"
          testId="admin-create-submit"
          isDisabled={busyId === "create" || !newUsername || !newPassword}
        >
          Create user
        </BrandButton>
      </form>

      {error ? (
        <p className="text-sm text-red-400" data-testid="admin-error">
          {error}
        </p>
      ) : null}

      <div className="overflow-x-auto rounded-xl border border-white/10">
        <table className="w-full text-left text-sm text-neutral-200">
          <thead className="bg-white/5 text-neutral-400">
            <tr>
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">Credits</th>
              <th className="px-3 py-2">Set balance</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t border-white/10">
                <td className="px-3 py-2">
                  <div className="font-medium text-white">{u.username}</div>
                  <div className="text-xs text-neutral-500">{u.email}</div>
                </td>
                <td className="px-3 py-2">
                  {u.credit_balance.toFixed(1)} / {u.credit_limit.toFixed(1)}
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <input
                      className="w-24 rounded border border-white/10 bg-black/30 px-2 py-1"
                      value={drafts[u.id] ?? String(u.credit_balance)}
                      onChange={(e) =>
                        setDrafts((prev) => ({
                          ...prev,
                          [u.id]: e.target.value,
                        }))
                      }
                      data-testid={`admin-credit-input-${u.username}`}
                    />
                    <BrandButton
                      type="button"
                      variant="primary"
                      testId={`admin-credit-save-${u.username}`}
                      isDisabled={busyId === u.id}
                      onClick={async () => {
                        const raw = drafts[u.id] ?? String(u.credit_balance);
                        const balance = Number(raw);
                        if (Number.isNaN(balance)) {
                          setError("Invalid balance");
                          return;
                        }
                        setBusyId(u.id);
                        try {
                          await setAdminUserCredits(u.id, { balance });
                          await reload();
                        } catch (err) {
                          setError(
                            err instanceof Error ? err.message : String(err),
                          );
                        } finally {
                          setBusyId(null);
                        }
                      }}
                    >
                      Save
                    </BrandButton>
                  </div>
                </td>
                <td className="px-3 py-2">
                  <BrandButton
                    type="button"
                    variant={u.is_active ? "ghost-danger" : "secondary"}
                    testId={`admin-toggle-${u.username}`}
                    isDisabled={busyId === u.id || u.id === me.id}
                    onClick={async () => {
                      setBusyId(u.id);
                      try {
                        await setAdminUserActive(u.id, !u.is_active);
                        await reload();
                      } catch (err) {
                        setError(
                          err instanceof Error ? err.message : String(err),
                        );
                      } finally {
                        setBusyId(null);
                      }
                    }}
                  >
                    {u.is_active ? "Disable" : "Enable"}
                  </BrandButton>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
