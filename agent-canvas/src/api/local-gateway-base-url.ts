const LOOPBACK_HOSTNAMES = new Set(["localhost", "127.0.0.1", "::1"]);

function trimTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, "");
}

function isLoopbackHostname(hostname: string): boolean {
  return LOOPBACK_HOSTNAMES.has(hostname.toLowerCase());
}

export function resolveLocalGatewayBaseUrl(): string {
  const explicit = import.meta.env.VITE_LOCAL_AUTH_BASE_URL?.trim();
  if (explicit) return trimTrailingSlashes(explicit);

  const envBase = readEnvBaseUrl();

  if (typeof window === "undefined") {
    return envBase ?? "";
  }

  const pageOrigin = trimTrailingSlashes(window.location.origin);
  if (!envBase) return pageOrigin;

  try {
    const target = new URL(envBase);
    const browserHost = new URL(pageOrigin).hostname;

    if (
      browserHost &&
      isLoopbackHostname(target.hostname) &&
      !isLoopbackHostname(browserHost)
    ) {
      return pageOrigin;
    }

    if (target.host !== new URL(pageOrigin).host) {
      return pageOrigin;
    }
  } catch {
    return pageOrigin;
  }

  return envBase;
}

function readEnvBaseUrl(): string | null {
  const baked = import.meta.env.VITE_BACKEND_BASE_URL?.trim();
  return baked ? trimTrailingSlashes(baked) : null;
}
