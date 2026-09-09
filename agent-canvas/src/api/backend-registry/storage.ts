import {
  SEEDED_DEFAULT_BACKEND_ID,
  makeDefaultLocalBackend,
  makeLockedCloudBackend,
} from "./default-backend";
import type {
  Backend,
  BackendAuthMode,
  BackendKind,
  BackendSelection,
} from "./types";

export const BACKENDS_STORAGE_KEY = "Creanova-backends";
export const ACTIVE_BACKEND_STORAGE_KEY = "Creanova-active-backend";

function isValidKind(value: unknown): value is BackendKind {
  return value === "local" || value === "cloud";
}

function isValidAuthMode(value: unknown): value is BackendAuthMode {
  return value === undefined || value === "api-key" || value === "cookie";
}

function isValidBackend(value: unknown): value is Backend {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Partial<Backend>;
  return (
    typeof v.id === "string" &&
    v.id.length > 0 &&
    typeof v.name === "string" &&
    typeof v.host === "string" &&
    typeof v.apiKey === "string" &&
    isValidKind(v.kind) &&
    isValidAuthMode(v.authMode)
  );
}

function isLoopbackUrl(value: string): boolean {
  try {
    const { hostname } = new URL(value);
    return (
      hostname === "localhost" ||
      hostname === "127.0.0.1" ||
      hostname === "::1" ||
      hostname === "[::1]"
    );
  } catch {
    return false;
  }
}

function hostnameOf(value: string): string | null {
  try {
    return new URL(value).hostname.toLowerCase();
  } catch {
    return null;
  }
}

/** Loopback or RFC 1918 / link-local — the bundled Canvas ingress, not a remote cloud host. */
function isPrivateOrLoopbackUrl(value: string): boolean {
  const hostname = hostnameOf(value);
  if (!hostname) return false;
  if (isLoopbackUrl(value)) return true;
  if (/^10\./.test(hostname)) return true;
  if (/^192\.168\./.test(hostname)) return true;
  if (/^172\.(1[6-9]|2\d|3[01])\./.test(hostname)) return true;
  if (/^fe[89ab][0-9a-f]:/i.test(hostname)) return true;
  if (/^f[cd][0-9a-f]{2}:/i.test(hostname)) return true;
  return false;
}

function shouldRewriteDefaultLocalHost(
  backend: Backend,
  defaultBackend: Backend,
): boolean {
  if (isLoopbackUrl(backend.host) || isLoopbackUrl(defaultBackend.host)) {
    return false;
  }
  const storedHost = hostnameOf(backend.host);
  const launcherHost = hostnameOf(defaultBackend.host);
  return (
    storedHost !== null &&
    storedHost === launcherHost &&
    isPrivateOrLoopbackUrl(backend.host) &&
    isPrivateOrLoopbackUrl(defaultBackend.host) &&
    backend.host !== defaultBackend.host
  );
}

function shouldSyncLauncherDefaultLocalBackend(
  backend: Backend,
  defaultBackend: Backend,
): boolean {
  if (backend.id !== SEEDED_DEFAULT_BACKEND_ID || backend.kind !== "local") {
    return false;
  }

  if (backend.host === defaultBackend.host) return true;
  if (isLoopbackUrl(backend.host) && isLoopbackUrl(defaultBackend.host)) {
    return true;
  }

  return shouldRewriteDefaultLocalHost(backend, defaultBackend);
}

function syncLauncherDefaultLocalBackend(backends: Backend[]): Backend[] {
  const defaultBackend = makeDefaultLocalBackend();
  if (!defaultBackend) return backends;

  let didSync = false;
  const syncedBackends = backends.map((backend) => {
    if (!shouldSyncLauncherDefaultLocalBackend(backend, defaultBackend)) {
      return backend;
    }

    const nextHost = shouldRewriteDefaultLocalHost(backend, defaultBackend)
      ? defaultBackend.host
      : backend.host;

    if (
      backend.apiKey === defaultBackend.apiKey &&
      backend.host === nextHost
    ) {
      return backend;
    }

    didSync = true;
    return {
      ...backend,
      host: nextHost,
      apiKey: defaultBackend.apiKey,
    };
  });

  if (!didSync) return backends;

  writeStoredBackends(syncedBackends);
  const hostRewritten = syncedBackends.some(
    (backend, index) => backend.host !== backends[index]?.host,
  );
  if (hostRewritten) {
    void import("./health-store").then((mod) => {
      mod.resetBackendHealth(SEEDED_DEFAULT_BACKEND_ID);
    });
  }
  return syncedBackends;
}

export function writeStoredBackends(backends: Backend[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(BACKENDS_STORAGE_KEY, JSON.stringify(backends));
  } catch {
    /* ignore quota / serialization errors */
  }
}

export function readStoredBackends(): Backend[] {
  if (typeof window === "undefined") return [];

  try {
    const lockedCloudBackend = makeLockedCloudBackend();
    if (lockedCloudBackend) {
      writeStoredBackends([lockedCloudBackend]);
      const activeSelection = readStoredActiveBackend();
      if (activeSelection?.backendId !== lockedCloudBackend.id) {
        writeStoredActiveBackend({ backendId: lockedCloudBackend.id });
      }
      return [lockedCloudBackend];
    }

    const raw = window.localStorage.getItem(BACKENDS_STORAGE_KEY);

    // First install: seed only when the launcher supplied enough information
    // for a usable local backend.
    if (raw === null) {
      const defaultBackend = makeDefaultLocalBackend();
      if (!defaultBackend) return [];

      writeStoredBackends([defaultBackend]);
      return [defaultBackend];
    }

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const valid = parsed.filter(isValidBackend);

    // If the stored array is empty (or everything in it failed validation),
    // only re-seed when the launcher supplied both a host and API key.
    if (valid.length === 0) {
      const defaultBackend = makeDefaultLocalBackend();
      if (!defaultBackend) return [];

      writeStoredBackends([defaultBackend]);
      return [defaultBackend];
    }

    const synced = syncLauncherDefaultLocalBackend(valid);
    return synced;
  } catch {
    return [];
  }
}

function parseBackendSelection(raw: string | null): BackendSelection | null {
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw);
    if (
      typeof parsed !== "object" ||
      parsed === null ||
      typeof (parsed as BackendSelection).backendId !== "string"
    ) {
      return null;
    }
    const orgIdRaw = (parsed as BackendSelection).orgId;
    return {
      backendId: (parsed as BackendSelection).backendId,
      orgId:
        typeof orgIdRaw === "string" && orgIdRaw.length > 0 ? orgIdRaw : null,
    };
  } catch {
    return null;
  }
}

function readStorageItem(
  storage: Storage | undefined,
  key: string,
): string | null {
  try {
    return storage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

function writeStorageItem(
  storage: Storage | undefined,
  key: string,
  value: string,
): void {
  try {
    storage?.setItem(key, value);
  } catch {
    /* ignore */
  }
}

function removeStorageItem(storage: Storage | undefined, key: string): void {
  try {
    storage?.removeItem(key);
  } catch {
    /* ignore */
  }
}

export function readStoredActiveBackend(): BackendSelection | null {
  if (typeof window === "undefined") return null;

  // Active backend is tab-scoped so reloading tab A does not adopt tab B's
  // backend. localStorage remains a last-used fallback for fresh tabs and old
  // persisted state.
  const sessionSelection = parseBackendSelection(
    readStorageItem(window.sessionStorage, ACTIVE_BACKEND_STORAGE_KEY),
  );
  if (sessionSelection) return sessionSelection;

  return parseBackendSelection(
    readStorageItem(window.localStorage, ACTIVE_BACKEND_STORAGE_KEY),
  );
}

export function writeStoredActiveBackend(
  selection: BackendSelection | null,
): void {
  if (typeof window === "undefined") return;

  if (!selection) {
    removeStorageItem(window.sessionStorage, ACTIVE_BACKEND_STORAGE_KEY);
    removeStorageItem(window.localStorage, ACTIVE_BACKEND_STORAGE_KEY);
    return;
  }

  const serialized = JSON.stringify({
    backendId: selection.backendId,
    orgId: selection.orgId ?? null,
  });
  // Mirror to localStorage only as the default for new tabs/backward
  // compatibility; reads in existing tabs prefer sessionStorage.
  writeStorageItem(
    window.sessionStorage,
    ACTIVE_BACKEND_STORAGE_KEY,
    serialized,
  );
  writeStorageItem(window.localStorage, ACTIVE_BACKEND_STORAGE_KEY, serialized);
}
