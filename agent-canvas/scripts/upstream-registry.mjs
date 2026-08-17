/**
 * Temporary upstream registry map.
 *
 * Creanova branding is used everywhere in this repo. Public npm/PyPI/GHCR
 * packages under the Creanova name are not published yet, so installers map
 * to the current OpenHands upstream artifacts here — and only here.
 *
 * When Creanova publishes its own packages/images, delete this file and use
 * the Creanova names directly.
 */
export const UPSTREAM_PYPI = {
  "creanova-agent-server": "openhands-agent-server",
  "creanova-automation": "openhands-automation",
  "creanova-sdk": "openhands-sdk",
  "creanova-tools": "openhands-tools",
  "creanova-workspace": "openhands-workspace",
};

export const UPSTREAM_GIT_SUBDIR = {
  "creanova-agent-server": "openhands-agent-server",
  "creanova-sdk": "openhands-sdk",
  "creanova-tools": "openhands-tools",
  "creanova-workspace": "openhands-workspace",
};

export const UPSTREAM_GIT_REPO =
  "https://github.com/OpenHands/software-agent-sdk";

export const UPSTREAM_IMAGES = {
  "ghcr.io/creanova/agent-server": "ghcr.io/openhands/agent-server",
  "ghcr.io/creanova/agent-canvas": "ghcr.io/openhands/agent-canvas",
};

/** @param {string} name */
export function pypiPackage(name) {
  return UPSTREAM_PYPI[name] ?? name;
}

/** @param {string} name */
export function gitSubdir(name) {
  return UPSTREAM_GIT_SUBDIR[name] ?? name;
}

/** @param {string} image */
export function containerImage(image) {
  const [repo, tag] = image.split(":");
  const mapped = UPSTREAM_IMAGES[repo] ?? repo;
  return tag ? `${mapped}:${tag}` : mapped;
}
