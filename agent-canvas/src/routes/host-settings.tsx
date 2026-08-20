import React from "react";
import { useSearchParams } from "react-router";
import {
  Server,
  Plus,
  Terminal,
  Trash2,
  KeyRound,
  ArrowLeftRight,
  FileCode2,
  ShieldCheck,
  ScrollText,
  Usb,
  Eye,
  EyeOff,
  Search,
  ChevronDown,
  PanelRightClose,
  PanelRightOpen,
  MoreHorizontal,
  Check,
  Home,
} from "lucide-react";
import "@xterm/xterm/css/xterm.css";
import { BrandButton } from "#/components/features/settings/brand-button";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import {
  createInfraServer,
  deleteInfraServer,
  fetchInfraServers,
  setInfraCredentials,
  updateInfraServer,
  type InfraServer,
} from "#/api/infra/client";
import { isLocalAuthEnabled } from "#/api/local-auth/client";
import { useLocalAuthUser } from "#/api/local-auth/hooks";
import { useSshTerminal } from "#/hooks/use-ssh-terminal";
import { useSettingsSectionHeader } from "#/contexts/settings-section-header-context";
import {
  formControlMultilineFieldClassName,
  formControlSettingsFieldClassName,
} from "#/utils/form-control-classes";
import { cn } from "#/utils/utils";

export const handle = { hideTitle: true };

type NavId =
  | "hosts"
  | "keychain"
  | "port-forwarding"
  | "snippets"
  | "known-hosts"
  | "logs"
  | "monitor";

type WorkspaceTab =
  | { kind: "vaults" }
  | { kind: "terminal"; id: string; serverId: string; title: string };

type Draft = {
  id: string | null; // null = new unsaved
  address: string;
  label: string;
  parentGroup: string;
  tags: string;
  port: string;
  username: string;
  password: string;
  authType: "password" | "key";
  privateKey: string;
};

const EMPTY_DRAFT = (): Draft => ({
  id: null,
  address: "",
  label: "",
  parentGroup: "",
  tags: "",
  port: "22",
  username: "",
  password: "",
  authType: "password",
  privateKey: "",
});

function draftFromServer(s: InfraServer): Draft {
  return {
    id: s.id,
    address: s.hostname,
    label: s.name,
    parentGroup: "",
    tags: (s.tags || []).join(", "),
    port: String(s.port || 22),
    username: s.username,
    password: "",
    authType: s.auth_type === "key" ? "key" : "password",
    privateKey: "",
  };
}

function MonitorPane({ gwBase }: { gwBase: string }) {
  const [frameKey, setFrameKey] = React.useState(0);
  const beszelSrc = React.useMemo(() => {
    const fromEnv = (
      import.meta.env.VITE_BESZEL_URL as string | undefined
    )?.replace(/\/+$/, "");
    if (fromEnv) {
      return `${fromEnv}/`;
    }
    // Prefer public Beszel UI (nginx injects All Systems). Fall back to GW proxy.
    if (typeof window !== "undefined") {
      const { protocol, hostname } = window.location;
      return `${protocol}//${hostname}:18090/`;
    }
    return `${gwBase}/beszel/`;
  }, [gwBase]);

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="flex items-center gap-1 border-b border-[var(--oh-border-subtle)] bg-base-secondary px-2 py-1">
        <button
          type="button"
          className="inline-flex size-8 items-center justify-center rounded-md text-tertiary-light hover:bg-interactive-hover hover:text-content"
          onClick={() => setFrameKey((k) => k + 1)}
          aria-label="All Systems"
          title="All Systems"
        >
          <Home className="size-[1.2rem]" strokeWidth={1.5} />
        </button>
      </div>
      <iframe
        key={frameKey}
        src={beszelSrc}
        title="Monitor"
        className="min-h-0 flex-1 border-0"
        allow="same-origin"
      />
    </div>
  );
}

const NAV: Array<{ id: NavId; label: string; icon: React.ReactNode }> = [
  { id: "hosts", label: "Hosts", icon: <Server className="size-4" /> },
  { id: "keychain", label: "Keychain", icon: <KeyRound className="size-4" /> },
  {
    id: "port-forwarding",
    label: "Port Forwarding",
    icon: <ArrowLeftRight className="size-4" />,
  },
  { id: "snippets", label: "Snippets", icon: <FileCode2 className="size-4" /> },
  {
    id: "known-hosts",
    label: "Known Hosts",
    icon: <ShieldCheck className="size-4" />,
  },
  { id: "logs", label: "Logs", icon: <ScrollText className="size-4" /> },
  { id: "monitor", label: "Monitor", icon: <Eye className="size-4" /> },
];

const fieldClass = cn(
  formControlSettingsFieldClassName,
  "caret-white [&:-webkit-autofill]:shadow-[inset_0_0_0_1000px_var(--oh-color-base-secondary)] [&:-webkit-autofill]:[-webkit-text-fill-color:white]",
);
const multilineClass = cn(
  formControlMultilineFieldClassName,
  "min-h-[100px] font-mono text-[11px]",
);
const labelClass = "mb-1 block text-xs text-tertiary-light";
const sectionTitleClass =
  "mb-2 text-xs font-medium uppercase tracking-wide text-tertiary-alt";
const chipBtnClass =
  "inline-flex items-center gap-1 rounded-lg border border-[var(--oh-border)] bg-base-secondary px-2 py-1 text-xs text-content hover:border-white/30 hover:text-white disabled:opacity-40";
const iconBtnClass =
  "rounded-md p-1.5 text-tertiary-alt hover:bg-interactive-hover hover:text-white";

/**
 * Settings → Host: Termius-inspired vault UI
 * (left nav · host list · host details · terminal tabs).
 */
export default function HostSettingsScreen() {
  const localAuth = isLocalAuthEnabled();
  const { data: me, isLoading: meLoading } = useLocalAuthUser();
  const { setHideSectionHeader } = useSettingsSectionHeader();
  const [searchParams, setSearchParams] = useSearchParams();

  const [nav, setNav] = React.useState<NavId>("hosts");
  const [servers, setServers] = React.useState<InfraServer[]>([]);
  const [listError, setListError] = React.useState<string | null>(null);
  const [filter, setFilter] = React.useState("");
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [draft, setDraft] = React.useState<Draft>(EMPTY_DRAFT);
  const [showPassword, setShowPassword] = React.useState(false);
  const [showAdvancedAuth, setShowAdvancedAuth] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [statusMsg, setStatusMsg] = React.useState<string | null>(null);
  const [savedDraft, setSavedDraft] = React.useState<Draft | null>(null);
  const [allChangesSaved, setAllChangesSaved] = React.useState(false);
  const [fontSize, setFontSize] = React.useState(13);
  /** Show / hide the New Host · Host Details panel */
  const [detailsOpen, setDetailsOpen] = React.useState(true);
  const [moreMenuOpen, setMoreMenuOpen] = React.useState(false);
  const moreMenuRef = React.useRef<HTMLDivElement>(null);

  const [workspaceTabs, setWorkspaceTabs] = React.useState<WorkspaceTab[]>([
    { kind: "vaults" },
  ]);
  const [activeWorkspace, setActiveWorkspace] = React.useState(0);

  const activeWs = workspaceTabs[activeWorkspace] ?? workspaceTabs[0];
  const terminalServerId =
    activeWs?.kind === "terminal" ? activeWs.serverId : null;
  const { containerRef, status, error, banner, reconnect, disconnect } =
    useSshTerminal(terminalServerId, { fontSize });

  const draftRef = React.useRef(draft);
  draftRef.current = draft;
  const showAdvancedAuthRef = React.useRef(showAdvancedAuth);
  showAdvancedAuthRef.current = showAdvancedAuth;

  React.useEffect(() => {
    setHideSectionHeader(true);
    return () => setHideSectionHeader(false);
  }, [setHideSectionHeader]);

  const reload = React.useCallback(async () => {
    if (!localAuth) return;
    try {
      setServers(await fetchInfraServers());
      setListError(null);
    } catch (err) {
      setListError(err instanceof Error ? err.message : String(err));
    }
  }, [localAuth]);

  React.useEffect(() => {
    if (me) void reload();
  }, [me, reload]);

  React.useEffect(() => {
    const sid = searchParams.get("server");
    if (!sid || !servers.length) return;
    const s = servers.find((x) => x.id === sid);
    if (!s) return;
    setSelectedId(s.id);
    const d = draftFromServer(s);
    setDraft(d);
    setSavedDraft(d);
    setAllChangesSaved(false);
    setSearchParams({}, { replace: true });
  }, [servers, searchParams, setSearchParams]);

  const hasPendingChanges = React.useMemo(() => {
    if (!savedDraft) {
      // New host: dirty if any meaningful field filled
      return !!(
        draft.address.trim() ||
        draft.label.trim() ||
        draft.username.trim() ||
        draft.password ||
        draft.privateKey.trim()
      );
    }
    return (
      draft.address !== savedDraft.address ||
      draft.label !== savedDraft.label ||
      draft.parentGroup !== savedDraft.parentGroup ||
      draft.tags !== savedDraft.tags ||
      draft.port !== savedDraft.port ||
      draft.username !== savedDraft.username ||
      draft.authType !== savedDraft.authType ||
      draft.password !== "" ||
      draft.privateKey !== ""
    );
  }, [draft, savedDraft]);

  const canEdit = Boolean(me?.is_admin);

  function selectHost(s: InfraServer) {
    setSelectedId(s.id);
    const d = draftFromServer(s);
    setDraft(d);
    setSavedDraft(d);
    setAllChangesSaved(false);
    setShowAdvancedAuth(s.auth_type === "key");
    setStatusMsg(null);
    setDetailsOpen(true);
    setActiveWorkspace(0);
  }

  function startNewHost() {
    setSelectedId(null);
    setDraft(EMPTY_DRAFT());
    setSavedDraft(null);
    setAllChangesSaved(false);
    setShowAdvancedAuth(false);
    setStatusMsg(null);
    setDetailsOpen(true);
    setActiveWorkspace(0);
    setNav("hosts");
  }

  function openTerminal(s: InfraServer) {
    setWorkspaceTabs((prev) => {
      const existingIdx = prev.findIndex(
        (t) => t.kind === "terminal" && t.serverId === s.id,
      );
      if (existingIdx >= 0) {
        setActiveWorkspace(existingIdx);
        return prev;
      }
      const tab: WorkspaceTab = {
        kind: "terminal",
        id: `${s.id}-${Date.now()}`,
        serverId: s.id,
        title: s.name || s.hostname,
      };
      setActiveWorkspace(prev.length);
      return [...prev, tab];
    });
  }

  function closeWorkspaceTab(index: number) {
    if (index === 0) return; // vaults stays
    setWorkspaceTabs((prev) => {
      const closing = prev[index];
      const next = prev.filter((_, i) => i !== index);
      if (closing?.kind === "terminal" && activeWs?.kind === "terminal") {
        const stillOpen = next.some(
          (t) => t.kind === "terminal" && t.serverId === closing.serverId,
        );
        if (!stillOpen) disconnect();
      }
      return next;
    });
    setActiveWorkspace((cur) => {
      if (cur === index) return Math.max(0, index - 1);
      if (cur > index) return cur - 1;
      return cur;
    });
  }

  const inFlightSaveRef = React.useRef<Promise<InfraServer | null> | null>(
    null,
  );

  const saveHost = React.useCallback(async (): Promise<InfraServer | null> => {
    if (!me?.is_admin) {
      setStatusMsg("Only admin can save hosts");
      return null;
    }
    if (inFlightSaveRef.current) {
      await inFlightSaveRef.current;
      return saveHost();
    }

    const snapshot = draftRef.current;
    const address = snapshot.address.trim();
    if (!address) {
      setStatusMsg("Address is required");
      return null;
    }
    const label = snapshot.label.trim() || address;
    const tags = snapshot.tags
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    const port = Number(snapshot.port) || 22;
    const username = snapshot.username.trim();
    if (!username) {
      setStatusMsg("Username is required");
      return null;
    }
    const authType =
      showAdvancedAuthRef.current && snapshot.privateKey.trim()
        ? "key"
        : snapshot.authType;
    const credential =
      authType === "key" ? snapshot.privateKey.trim() : snapshot.password;

    const work = (async (): Promise<InfraServer | null> => {
      setSaving(true);
      setStatusMsg(null);
      try {
        let saved: InfraServer;
        if (snapshot.id) {
          saved = await updateInfraServer(snapshot.id, {
            name: label,
            hostname: address,
            port,
            username,
            auth_type: authType,
            tags,
          });
          if (credential) {
            await setInfraCredentials(snapshot.id, {
              credential,
              auth_type: authType,
            });
          }
        } else {
          saved = await createInfraServer({
            name: label,
            hostname: address,
            port,
            username,
            auth_type: authType,
            tags,
            credential: credential || undefined,
          });
        }
        await reload();
        setSelectedId(saved.id);
        const updatedDraft = draftFromServer(saved);
        setDraft((d) => {
          const next = { ...d, id: saved.id };
          if (d.password === snapshot.password && credential) {
            next.password = "";
          }
          if (d.privateKey === snapshot.privateKey && credential) {
            next.privateKey = "";
          }
          draftRef.current = next;
          return next;
        });
        setSavedDraft(updatedDraft);
        setAllChangesSaved(true);
        return saved;
      } catch (err) {
        setStatusMsg(err instanceof Error ? err.message : String(err));
        return null;
      } finally {
        setSaving(false);
      }
    })();

    inFlightSaveRef.current = work;
    try {
      return await work;
    } finally {
      if (inFlightSaveRef.current === work) {
        inFlightSaveRef.current = null;
      }
    }
  }, [me?.is_admin, reload]);

  React.useEffect(() => {
    if (!canEdit || !hasPendingChanges) return;
    if (!draft.address.trim() || !draft.username.trim()) return;
    const timer = window.setTimeout(() => {
      void saveHost();
    }, 700);
    return () => window.clearTimeout(timer);
  }, [
    canEdit,
    draft.address,
    draft.label,
    draft.parentGroup,
    draft.tags,
    draft.port,
    draft.username,
    draft.password,
    draft.privateKey,
    draft.authType,
    draft.id,
    hasPendingChanges,
    saveHost,
  ]);

  async function connect() {
    let target: InfraServer | null = null;
    if (draft.id) {
      target = servers.find((s) => s.id === draft.id) || null;
      if (me?.is_admin && hasPendingChanges) {
        target = (await saveHost()) || target;
      }
    } else {
      target = await saveHost();
    }
    if (!target && draft.id) {
      target = servers.find((s) => s.id === draft.id) || null;
    }
    if (!target) {
      if (!statusMsg) setStatusMsg("Fill address and username to connect");
      return;
    }
    openTerminal(target);
  }

  async function removeHost() {
    if (!draft.id) return;
    if (!confirm(`Remove host ${draft.label || draft.address}?`)) return;
    try {
      await deleteInfraServer(draft.id);
      setWorkspaceTabs((prev) =>
        prev.filter((t) => !(t.kind === "terminal" && t.serverId === draft.id)),
      );
      startNewHost();
      await reload();
    } catch (err) {
      setStatusMsg(err instanceof Error ? err.message : String(err));
    }
  }

  React.useEffect(() => {
    if (!moreMenuOpen) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!moreMenuRef.current?.contains(event.target as Node)) {
        setMoreMenuOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMoreMenuOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [moreMenuOpen]);

  if (!localAuth) {
    return (
      <p className="text-sm text-tertiary-light">
        Host / SSH requires local auth gateway (
        <code className="text-xs">OH_LOCAL_AUTH=1</code>).
      </p>
    );
  }

  if (meLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner size="large" />
      </div>
    );
  }

  const filtered = servers.filter((s) => {
    const q = filter.trim().toLowerCase();
    if (!q) return true;
    return (
      s.name.toLowerCase().includes(q) ||
      s.hostname.toLowerCase().includes(q) ||
      s.username.toLowerCase().includes(q) ||
      (s.tags || []).some((t) => t.toLowerCase().includes(q))
    );
  });

  const stubCopy: Record<Exclude<NavId, "hosts" | "monitor">, string> = {
    keychain: "Store reusable passwords and SSH keys (coming soon).",
    "port-forwarding": "Local / remote / dynamic tunnels (coming soon).",
    snippets: "Reusable command snippets for sessions (coming soon).",
    "known-hosts": "Manage host key fingerprints (coming soon).",
    logs: "Connection and session audit log (coming soon).",
  };

  const gwBase = (() => {
    const base =
      (import.meta.env.VITE_LOCAL_AUTH_BASE_URL as string | undefined) ||
      (import.meta.env.VITE_BACKEND_BASE_URL as string | undefined) ||
      "";
    return base.replace(/\/+$/, "");
  })();

  return (
    <div
      data-testid="settings-host"
      className="flex h-[calc(100vh-6rem)] min-h-[480px] w-full flex-col overflow-hidden rounded-xl border border-[var(--oh-border-subtle)] bg-base text-content"
    >
      <div className="flex items-center gap-0.5 border-b border-[var(--oh-border-subtle)] bg-base-secondary px-2 pt-1.5">
        {workspaceTabs.map((tab, i) => (
          <div
            key={tab.kind === "vaults" ? "vaults" : tab.id}
            className={cn(
              "group flex items-center gap-1.5 rounded-t-md px-3 py-1.5 text-xs",
              i === activeWorkspace
                ? "bg-base text-white"
                : "text-tertiary-alt hover:bg-interactive-hover hover:text-content",
            )}
          >
            <button type="button" onClick={() => setActiveWorkspace(i)}>
              {tab.kind === "vaults" ? "Vaults" : tab.title}
            </button>
            {tab.kind === "terminal" ? (
              <button
                type="button"
                className="text-tertiary-alt hover:text-danger"
                aria-label="Close tab"
                onClick={() => closeWorkspaceTab(i)}
              >
                ×
              </button>
            ) : null}
          </div>
        ))}
        <span className="ml-auto px-2 pb-1 text-[10px] text-tertiary-alt">
          SFTP soon
        </span>
      </div>

      {activeWs?.kind === "terminal" ? (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="flex items-center justify-between border-b border-[var(--oh-border-subtle)] bg-base-secondary px-3 py-1.5 text-[11px] text-tertiary-light">
            <span className="truncate">
              {banner || activeWs.title} · {status}
              {error ? ` · ${error}` : ""}
            </span>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1">
                Font
                <select
                  className={cn(fieldClass, "h-8 w-auto px-2")}
                  value={fontSize}
                  onChange={(e) => setFontSize(Number(e.target.value))}
                >
                  {[11, 12, 13, 14, 16, 18].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <BrandButton
                type="button"
                variant="secondary"
                onClick={reconnect}
              >
                Reconnect
              </BrandButton>
            </div>
          </div>
          <div className="min-h-0 flex-1 bg-base p-2">
            <div
              ref={containerRef}
              className="h-full w-full overflow-hidden rounded-lg border border-[var(--oh-border-subtle)]"
            />
          </div>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1">
          <nav className="flex w-[148px] shrink-0 flex-col gap-0.5 border-r border-[var(--oh-border-subtle)] bg-base-secondary p-2">
            {NAV.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setNav(item.id)}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm",
                  nav === item.id
                    ? "bg-interactive-hover text-white"
                    : "text-tertiary-light hover:bg-interactive-hover-low hover:text-content",
                )}
              >
                <span
                  className={cn(
                    nav === item.id ? "text-primary" : "text-tertiary-alt",
                  )}
                >
                  {item.icon}
                </span>
                {item.label}
              </button>
            ))}
          </nav>

          {nav === "monitor" ? (
            <MonitorPane gwBase={gwBase} />
          ) : nav !== "hosts" ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-2 px-8 text-center text-tertiary-light">
              <p className="text-base text-content">
                {NAV.find((n) => n.id === nav)?.label}
              </p>
              {/* eslint-disable-next-line i18next/no-literal-string */}
              <p className="max-w-sm text-sm">
                {stubCopy[nav as Exclude<NavId, "hosts" | "monitor">]}
              </p>
            </div>
          ) : (
            <>
              <section className="flex min-w-0 flex-1 flex-col border-r border-[var(--oh-border-subtle)] bg-base">
                <div className="space-y-2 border-b border-[var(--oh-border-subtle)] p-3">
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-2.5 top-1/2 z-[1] size-3.5 -translate-y-1/2 text-tertiary-alt" />
                    <input
                      className={cn(fieldClass, "pl-8")}
                      placeholder="Find a host or ssh user@hostname…"
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {canEdit ? (
                      <button
                        type="button"
                        onClick={startNewHost}
                        className={chipBtnClass}
                      >
                        <Plus className="size-3.5" /> New host
                      </button>
                    ) : null}
                    <button
                      type="button"
                      disabled={!selectedId}
                      onClick={() => {
                        const s = servers.find((x) => x.id === selectedId);
                        if (s) openTerminal(s);
                      }}
                      className={chipBtnClass}
                    >
                      <Terminal className="size-3.5" /> Terminal
                    </button>
                    <button
                      type="button"
                      disabled
                      title="Serial connections coming soon"
                      className={cn(chipBtnClass, "opacity-50")}
                    >
                      <Usb className="size-3.5" /> Serial
                    </button>
                    {!detailsOpen ? (
                      <button
                        type="button"
                        onClick={() => setDetailsOpen(true)}
                        className={chipBtnClass}
                      >
                        <PanelRightOpen className="size-3.5" /> Details
                      </button>
                    ) : null}
                  </div>
                </div>

                {listError ? (
                  <p className="px-3 py-2 text-xs text-danger">{listError}</p>
                ) : null}

                <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                  <p className="px-3 pt-2 text-sm font-medium text-white">
                    Hosts
                  </p>
                  <ul className="grid flex-1 auto-rows-min grid-cols-[repeat(auto-fill,minmax(220px,1fr))] content-start gap-3 overflow-y-auto p-3 pt-2">
                    {filtered.map((s) => (
                      <li key={s.id} className="min-w-0">
                        <button
                          type="button"
                          onClick={() => selectHost(s)}
                          onDoubleClick={() => openTerminal(s)}
                          className={cn(
                            "flex w-full min-h-[72px] items-center gap-3 rounded-2xl border px-3.5 py-3.5 text-left transition-colors",
                            selectedId === s.id
                              ? "border-primary/60 bg-interactive-hover shadow-[inset_0_0_0_1px_rgba(255,255,255,0.04)]"
                              : "border-[var(--oh-border-subtle)] bg-base-secondary hover:border-[var(--oh-border)] hover:bg-interactive-hover-low",
                          )}
                        >
                          <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-[color-mix(in_srgb,var(--oh-color-primary)_22%,var(--oh-color-base-secondary))] text-primary ring-1 ring-primary/35">
                            <Server className="size-[18px]" strokeWidth={2} />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-base font-medium leading-snug text-white">
                              {s.name || s.hostname}
                            </span>
                            <span className="mt-0.5 block truncate text-[10px] leading-tight text-tertiary-light">
                              {s.hostname}
                              {s.username ? ` · ${s.username}` : ""}
                            </span>
                          </span>
                          <span className="shrink-0 rounded-md border border-[var(--oh-border-subtle)] bg-interactive-hover/60 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide text-tertiary-alt">
                            ssh
                          </span>
                        </button>
                      </li>
                    ))}
                    {!filtered.length ? (
                      <li className="col-span-full px-2 py-8 text-center text-xs leading-relaxed text-tertiary-alt">
                        {canEdit
                          ? "No hosts yet. Click + New host to add one."
                          : "No hosts granted. Ask an admin to add and grant access."}
                      </li>
                    ) : null}
                  </ul>
                </div>
              </section>

              {detailsOpen ? (
                <section className="flex w-1/4 max-w-[25%] min-w-[260px] shrink-0 flex-col bg-base-secondary">
                  <div className="flex items-start justify-between gap-3 border-b border-[var(--oh-border-subtle)] px-4 py-2.5">
                    <div className="min-w-0">
                      <h2 className="truncate text-sm font-medium text-white">
                        {draft.id
                          ? draft.label.trim() ||
                            draft.address ||
                            "Host Details"
                          : "New Host"}
                      </h2>
                      <button
                        type="button"
                        className="mt-0.5 inline-flex items-center gap-1 text-xs text-tertiary-light hover:text-content"
                      >
                        Personal vault
                        <ChevronDown className="size-3.5 opacity-70" />
                      </button>
                    </div>
                    <div className="flex shrink-0 items-center gap-0.5">
                      {saving ? (
                        <span
                          className="px-1.5 py-1 text-[10px] text-tertiary-alt"
                          aria-label="Saving"
                        >
                          Saving…
                        </span>
                      ) : allChangesSaved && !hasPendingChanges ? (
                        <span
                          className="flex items-center gap-1 rounded-md px-1.5 py-1 text-xs text-success"
                          title="All changes saved"
                          aria-label="All changes saved"
                        >
                          <Check className="size-3.5" />
                        </span>
                      ) : null}
                      <div className="relative" ref={moreMenuRef}>
                        <button
                          type="button"
                          className={iconBtnClass}
                          aria-label="More"
                          aria-expanded={moreMenuOpen}
                          aria-haspopup="menu"
                          title="More"
                          data-testid="host-details-more"
                          onClick={() => setMoreMenuOpen((open) => !open)}
                        >
                          <MoreHorizontal className="size-4" />
                        </button>
                        {moreMenuOpen ? (
                          <div
                            role="menu"
                            data-testid="host-details-more-menu"
                            className="absolute right-0 z-20 mt-1 min-w-[148px] rounded-lg border border-[var(--oh-border)] bg-base-secondary py-1 shadow-lg"
                          >
                            <button
                              type="button"
                              role="menuitem"
                              className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-content hover:bg-interactive-hover disabled:opacity-40"
                              disabled={saving || (!draft.id && !canEdit)}
                              onClick={() => {
                                setMoreMenuOpen(false);
                                void connect();
                              }}
                            >
                              <Terminal className="size-3.5" />
                              Connect
                            </button>
                            {canEdit && draft.id ? (
                              <button
                                type="button"
                                role="menuitem"
                                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-danger hover:bg-interactive-hover"
                                onClick={() => {
                                  setMoreMenuOpen(false);
                                  void removeHost();
                                }}
                              >
                                <Trash2 className="size-3.5" />
                                Remove
                              </button>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                      <button
                        type="button"
                        className={iconBtnClass}
                        aria-label="Close host details"
                        title="Close"
                        onClick={() => setDetailsOpen(false)}
                      >
                        <PanelRightClose className="size-4" />
                      </button>
                    </div>
                  </div>

                  <div className="flex-1 overflow-y-auto px-4 py-3">
                    <div className="flex w-full flex-col gap-3">
                      <div>
                        <label className={labelClass} htmlFor="host-address">
                          Address
                        </label>
                        <input
                          id="host-address"
                          className={fieldClass}
                          placeholder="192.168.1.250 or host.example.com"
                          value={draft.address}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              address: e.target.value,
                            }))
                          }
                          disabled={!canEdit && !!draft.id}
                        />
                      </div>

                      <div>
                        <p className={sectionTitleClass}>General</p>
                        <div className="space-y-2.5">
                          <div>
                            <label className={labelClass} htmlFor="host-label">
                              Label
                            </label>
                            <input
                              id="host-label"
                              className={fieldClass}
                              placeholder="Friendly name"
                              value={draft.label}
                              onChange={(e) =>
                                setDraft((d) => ({
                                  ...d,
                                  label: e.target.value,
                                }))
                              }
                              disabled={!canEdit && !!draft.id}
                            />
                          </div>
                          <div>
                            <label className={labelClass} htmlFor="host-group">
                              Parent Group
                            </label>
                            <input
                              id="host-group"
                              className={fieldClass}
                              placeholder="Optional folder (UI only for now)"
                              value={draft.parentGroup}
                              onChange={(e) =>
                                setDraft((d) => ({
                                  ...d,
                                  parentGroup: e.target.value,
                                }))
                              }
                              disabled={!canEdit}
                            />
                          </div>
                          <div>
                            <label className={labelClass} htmlFor="host-tags">
                              Tags
                            </label>
                            <input
                              id="host-tags"
                              className={fieldClass}
                              placeholder="prod, gpu (comma-separated)"
                              value={draft.tags}
                              onChange={(e) =>
                                setDraft((d) => ({
                                  ...d,
                                  tags: e.target.value,
                                }))
                              }
                              disabled={!canEdit && !!draft.id}
                            />
                          </div>
                        </div>
                      </div>

                      <div>
                        <label className={labelClass} htmlFor="host-port">
                          SSH on{" "}
                          <span className="text-primary">
                            [{draft.port || "22"}]
                          </span>{" "}
                          port
                        </label>
                        <input
                          id="host-port"
                          className={cn(fieldClass, "w-24")}
                          value={draft.port}
                          onChange={(e) =>
                            setDraft((d) => ({ ...d, port: e.target.value }))
                          }
                          disabled={!canEdit && !!draft.id}
                        />
                      </div>

                      <div>
                        <p className={sectionTitleClass}>Credentials</p>
                        <div className="space-y-2.5">
                          <div>
                            <label
                              className={labelClass}
                              htmlFor="host-username"
                            >
                              Username
                            </label>
                            <input
                              id="host-username"
                              className={fieldClass}
                              value={draft.username}
                              onChange={(e) =>
                                setDraft((d) => ({
                                  ...d,
                                  username: e.target.value,
                                }))
                              }
                              disabled={!canEdit && !!draft.id}
                              autoComplete="username"
                            />
                          </div>
                          <div>
                            <label
                              className={labelClass}
                              htmlFor="host-password"
                            >
                              Password
                              {draft.id ? (
                                <span className="ml-1 font-normal text-tertiary-alt">
                                  (leave blank to keep stored)
                                </span>
                              ) : null}
                            </label>
                            <div className="relative">
                              <input
                                id="host-password"
                                name="host-password"
                                type={showPassword ? "text" : "password"}
                                className={cn(
                                  fieldClass,
                                  // Keep dots/caret visible even after browser autofill
                                  // leaves a stuck -webkit-text-fill-color.
                                  "pr-10 text-white caret-white [-webkit-text-fill-color:white]",
                                )}
                                value={draft.password}
                                onChange={(e) =>
                                  setDraft((d) => ({
                                    ...d,
                                    password: e.target.value,
                                    authType: "password",
                                  }))
                                }
                                // disabled (not readOnly): readOnly looks editable
                                // but swallows keystrokes when !canEdit.
                                disabled={!canEdit}
                                placeholder={
                                  canEdit ? "SSH password" : "Admin only"
                                }
                                autoComplete="new-password"
                                spellCheck={false}
                              />
                              <button
                                type="button"
                                tabIndex={-1}
                                disabled={!canEdit}
                                className="absolute right-2 top-1/2 z-[1] -translate-y-1/2 text-tertiary-alt hover:text-white disabled:opacity-40"
                                onClick={() => setShowPassword((v) => !v)}
                                aria-label={
                                  showPassword
                                    ? "Hide password"
                                    : "Show password"
                                }
                              >
                                {showPassword ? (
                                  <EyeOff className="size-4" />
                                ) : (
                                  <Eye className="size-4" />
                                )}
                              </button>
                            </div>
                            {!canEdit ? (
                              <p className="mt-1 text-[11px] text-tertiary-alt">
                                Only an admin can set or update the SSH
                                password.
                              </p>
                            ) : null}
                          </div>
                          <button
                            type="button"
                            className="text-xs text-primary hover:underline"
                            onClick={() => setShowAdvancedAuth((v) => !v)}
                          >
                            {showAdvancedAuth ? "−" : "+"} SSH ID, Key,
                            Certificate, FIDO2
                          </button>
                          {showAdvancedAuth ? (
                            <div>
                              <label
                                className={labelClass}
                                htmlFor="host-private-key"
                              >
                                Private key (PEM)
                              </label>
                              <textarea
                                id="host-private-key"
                                className={multilineClass}
                                placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
                                value={draft.privateKey}
                                onChange={(e) =>
                                  setDraft((d) => ({
                                    ...d,
                                    privateKey: e.target.value,
                                    authType: "key",
                                  }))
                                }
                                disabled={!canEdit}
                              />
                            </div>
                          ) : null}
                        </div>
                      </div>

                      {statusMsg ? (
                        <p
                          className={cn(
                            "text-xs",
                            statusMsg === "Saved"
                              ? "text-success"
                              : "text-primary",
                          )}
                        >
                          {statusMsg}
                        </p>
                      ) : null}
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-2 border-t border-[var(--oh-border-subtle)] px-4 py-2.5">
                    <BrandButton
                      type="button"
                      variant="primary"
                      className="min-w-[100px]"
                      isDisabled={saving || (!draft.id && !canEdit)}
                      onClick={() => void connect()}
                    >
                      Connect
                    </BrandButton>
                  </div>
                </section>
              ) : null}
            </>
          )}
        </div>
      )}
    </div>
  );
}
