import React from "react";
import { Link, Navigate } from "react-router";
import { BrandButton } from "#/components/features/settings/brand-button";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import {
  createInfraServer,
  fetchInfraServers,
  testInfraServer,
  type InfraServer,
} from "#/api/infra/client";
import { isLocalAuthEnabled } from "#/api/local-auth/client";
import { useLocalAuthUser } from "#/api/local-auth/hooks";

export default function InfraServersScreen() {
  const enabled = isLocalAuthEnabled();
  const { data: me, isLoading } = useLocalAuthUser();
  const [servers, setServers] = React.useState<InfraServer[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [name, setName] = React.useState("");
  const [hostname, setHostname] = React.useState("");
  const [username, setUsername] = React.useState("");
  const [credential, setCredential] = React.useState("");

  const reload = React.useCallback(async () => {
    setError(null);
    try {
      setServers(await fetchInfraServers());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  React.useEffect(() => {
    if (me) void reload();
  }, [me, reload]);

  if (!enabled) return <Navigate to="/" replace />;
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }
  if (!me?.is_admin) return <Navigate to="/" replace />;

  return (
    <div
      className="mx-auto flex w-full max-w-4xl flex-col gap-4 p-6"
      data-testid="infra-servers"
    >
      <h1 className="text-xl font-semibold text-white">
        Infrastructure servers
      </h1>
      <p className="text-sm text-neutral-400">
        SSH inventory for GPU / service tools. Credentials are encrypted and
        never shown again.
      </p>
      {error ? <p className="text-sm text-red-400">{error}</p> : null}

      <form
        className="grid grid-cols-1 gap-2 md:grid-cols-2"
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          try {
            await createInfraServer({
              name: name.trim(),
              hostname: hostname.trim(),
              username: username.trim(),
              auth_type: "password",
              credential: credential || undefined,
            });
            setName("");
            setHostname("");
            setUsername("");
            setCredential("");
            await reload();
          } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
          }
        }}
      >
        <input
          className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm"
          placeholder="name (gpu-01)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm"
          placeholder="hostname"
          value={hostname}
          onChange={(e) => setHostname(e.target.value)}
          required
        />
        <input
          className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm"
          placeholder="ssh username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />
        <input
          className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm"
          placeholder="password or leave empty"
          type="password"
          value={credential}
          onChange={(e) => setCredential(e.target.value)}
        />
        <BrandButton type="submit" variant="primary" className="md:col-span-2">
          Add server
        </BrandButton>
      </form>

      <ul className="divide-y divide-neutral-800 rounded border border-neutral-800">
        {servers.map((s) => (
          <li
            key={s.id}
            className="flex items-center justify-between gap-2 px-3 py-2 text-sm"
          >
            <div>
              <Link
                className="text-white underline"
                to={`/admin/infra/${s.id}`}
              >
                {s.name}
              </Link>
              <div className="text-xs text-neutral-400">
                {s.username}@{s.hostname}:{s.port}
                {s.last_error ? ` · err: ${s.last_error}` : ""}
              </div>
            </div>
            <div className="flex gap-1">
              <Link
                to={`/admin/ssh?server=${s.id}`}
                className="rounded border border-neutral-700 px-2 py-1 text-xs text-sky-300 hover:bg-neutral-800"
              >
                SSH
              </Link>
              <BrandButton
                type="button"
                variant="secondary"
                onClick={async () => {
                  try {
                    const r = await testInfraServer(s.id);
                    setError(
                      r.ok
                        ? `Test OK (${r.duration_ms ?? "?"}ms)`
                        : `Test failed: ${r.stdout || "no output"}`,
                    );
                    await reload();
                  } catch (err) {
                    setError(err instanceof Error ? err.message : String(err));
                  }
                }}
              >
                Test
              </BrandButton>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
