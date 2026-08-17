import React from "react";
import { Link, Navigate, useSearchParams } from "react-router";
import "@xterm/xterm/css/xterm.css";
import { BrandButton } from "#/components/features/settings/brand-button";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import { fetchInfraServers, type InfraServer } from "#/api/infra/client";
import { isLocalAuthEnabled } from "#/api/local-auth/client";
import { useLocalAuthUser } from "#/api/local-auth/hooks";
import { useSshTerminal } from "#/hooks/use-ssh-terminal";

type Tab = {
  id: string;
  serverId: string;
  title: string;
};

/**
 * Terminus-style SSH workspace: host sidebar + session tabs + xterm.
 */
export default function InfraSshWorkspace() {
  const enabled = isLocalAuthEnabled();
  const { data: me, isLoading } = useLocalAuthUser();
  const [searchParams, setSearchParams] = useSearchParams();
  const [servers, setServers] = React.useState<InfraServer[]>([]);
  const [tabs, setTabs] = React.useState<Tab[]>([]);
  const [activeTabId, setActiveTabId] = React.useState<string | null>(null);
  const [listError, setListError] = React.useState<string | null>(null);
  const [filter, setFilter] = React.useState("");

  const activeTab = tabs.find((t) => t.id === activeTabId) || null;
  const { containerRef, status, error, banner, reconnect } = useSshTerminal(
    activeTab?.serverId ?? null,
  );

  React.useEffect(() => {
    if (!me) return;
    void (async () => {
      try {
        setServers(await fetchInfraServers());
      } catch (err) {
        setListError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, [me]);

  // Deep-link ?server=<id>
  React.useEffect(() => {
    const sid = searchParams.get("server");
    if (!sid || !servers.length) return;
    const s = servers.find((x) => x.id === sid);
    if (!s) return;
    openServer(s);
    setSearchParams({}, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [servers, searchParams]);

  function openServer(s: InfraServer) {
    const existing = tabs.find((t) => t.serverId === s.id);
    if (existing) {
      setActiveTabId(existing.id);
      return;
    }
    const tab: Tab = {
      id: `${s.id}-${Date.now()}`,
      serverId: s.id,
      title: s.name,
    };
    setTabs((prev) => [...prev, tab]);
    setActiveTabId(tab.id);
  }

  function closeTab(id: string) {
    setTabs((prev) => {
      const next = prev.filter((t) => t.id !== id);
      if (activeTabId === id) {
        setActiveTabId(next.length ? next[next.length - 1].id : null);
      }
      return next;
    });
  }

  if (!enabled) return <Navigate to="/" replace />;
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }
  if (!me) return <Navigate to="/login" replace />;

  const filtered = servers.filter((s) => {
    const q = filter.trim().toLowerCase();
    if (!q) return true;
    return (
      s.name.toLowerCase().includes(q) ||
      s.hostname.toLowerCase().includes(q) ||
      s.username.toLowerCase().includes(q)
    );
  });

  return (
    <div
      className="flex h-[calc(100vh-3rem)] min-h-[480px] w-full overflow-hidden bg-[#08090c] text-neutral-200"
      data-testid="infra-ssh-workspace"
    >
      {/* Host list — Terminus-style sidebar */}
      <aside className="flex w-64 shrink-0 flex-col border-r border-[#1a1d24] bg-[#0c0e12]">
        <div className="flex items-center justify-between border-b border-[#1a1d24] px-3 py-2">
          <h1 className="text-sm font-semibold tracking-wide text-white">
            SSH
          </h1>
          <Link
            to="/admin/infra"
            className="text-[11px] text-sky-400 hover:underline"
          >
            Manage
          </Link>
        </div>
        <div className="border-b border-[#1a1d24] px-2 py-2">
          <input
            className="w-full rounded border border-[#2a2f3a] bg-[#12151c] px-2 py-1 text-xs text-neutral-200 outline-none focus:border-sky-600"
            placeholder="Filter hosts…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        {listError ? (
          <p className="px-3 py-2 text-xs text-red-400">{listError}</p>
        ) : null}
        <ul className="flex-1 overflow-y-auto py-1">
          {filtered.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => openServer(s)}
                className={`flex w-full flex-col gap-0.5 px-3 py-2 text-left hover:bg-[#161a22] ${
                  activeTab?.serverId === s.id ? "bg-[#161a22]" : ""
                }`}
              >
                <span className="truncate text-sm text-white">{s.name}</span>
                <span className="truncate text-[11px] text-neutral-500">
                  {s.username}@{s.hostname}:{s.port}
                </span>
              </button>
            </li>
          ))}
          {!filtered.length ? (
            <li className="px-3 py-4 text-xs text-neutral-500">
              No hosts. Add one in{" "}
              <Link to="/admin/infra" className="text-sky-400 underline">
                Admin · infra
              </Link>
              .
            </li>
          ) : null}
        </ul>
      </aside>

      {/* Main: tabs + terminal */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-1 overflow-x-auto border-b border-[#1a1d24] bg-[#0c0e12] px-1">
          {tabs.map((t) => (
            <div
              key={t.id}
              className={`group flex items-center gap-1 rounded-t px-2 py-1.5 text-xs ${
                t.id === activeTabId
                  ? "bg-[#12151c] text-white"
                  : "text-neutral-400 hover:bg-[#12151c]/60"
              }`}
            >
              <button type="button" onClick={() => setActiveTabId(t.id)}>
                {t.title}
              </button>
              <button
                type="button"
                className="ml-1 text-neutral-600 hover:text-red-400"
                onClick={() => closeTab(t.id)}
                aria-label="Close tab"
              >
                ×
              </button>
            </div>
          ))}
          {!tabs.length ? (
            <span className="px-3 py-2 text-xs text-neutral-500">
              Select a host to open an SSH session
            </span>
          ) : null}
        </div>

        <div className="flex items-center justify-between border-b border-[#1a1d24] bg-[#0c0e12] px-3 py-1 text-[11px] text-neutral-500">
          <span>
            {banner || activeTab?.title || "—"} · {status}
            {error ? ` · ${error}` : ""}
          </span>
          {activeTab ? (
            <BrandButton type="button" variant="secondary" onClick={reconnect}>
              Reconnect
            </BrandButton>
          ) : null}
        </div>

        <div className="relative min-h-0 flex-1 bg-[#0c0e12] p-2">
          {activeTab ? (
            <div
              ref={containerRef}
              className="h-full w-full overflow-hidden rounded border border-[#1a1d24]"
            />
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-neutral-500">
              <p className="text-sm">Creanova SSH</p>
              <p className="max-w-sm text-center text-xs">
                Terminus-style workspace. Hosts come from infra inventory;
                credentials stay on the gateway.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
