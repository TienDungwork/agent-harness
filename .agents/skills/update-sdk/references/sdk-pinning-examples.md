# SDK Pinning Examples

Examples from real commits showing how to pin SDK packages to unreleased commits, branches, or released versions.

## Pin to a Specific Commit

Example from commit `169fb76` (pinning all 3 packages to SDK commit `100e9af`):

### `dependencies` array (PEP 508 format)

```toml
"Creanova-agent-server @ git+https://github.com/Creanova/software-agent-sdk.git@100e9af#subdirectory=Creanova-agent-server",
"Creanova-sdk @ git+https://github.com/Creanova/software-agent-sdk.git@100e9af#subdirectory=Creanova-sdk",
"Creanova-tools @ git+https://github.com/Creanova/software-agent-sdk.git@100e9af#subdirectory=Creanova-tools",
```

### `[tool.poetry.dependencies]` (Poetry format)

```toml
Creanova-sdk = { git = "https://github.com/Creanova/software-agent-sdk.git", rev = "100e9af", subdirectory = "Creanova-sdk" }
Creanova-agent-server = { git = "https://github.com/Creanova/software-agent-sdk.git", rev = "100e9af", subdirectory = "Creanova-agent-server" }
Creanova-tools = { git = "https://github.com/Creanova/software-agent-sdk.git", rev = "100e9af", subdirectory = "Creanova-tools" }
```

### `Creanova/app_server/sandbox/sandbox_spec_service.py`

```python
AGENT_SERVER_IMAGE = 'ghcr.io/Creanova/agent-server:<merge-commit-sha>-python'
```

**⚠️ Important:** The image tag is the **merge-commit SHA** from the SDK CI, not the commit hash used in `pyproject.toml`. Look up the correct tag from the SDK PR description or CI logs.

## Pin to a Branch

Example from commit `430ee1c` (pinning to branch `Creanova/issue-2228-sdk-settings-schema`):

### `[tool.poetry.dependencies]`

```toml
Creanova-sdk = { git = "https://github.com/Creanova/software-agent-sdk.git", branch = "Creanova/issue-2228-sdk-settings-schema", subdirectory = "Creanova-sdk" }
Creanova-agent-server = { git = "https://github.com/Creanova/software-agent-sdk.git", branch = "Creanova/issue-2228-sdk-settings-schema", subdirectory = "Creanova-agent-server" }
Creanova-tools = { git = "https://github.com/Creanova/software-agent-sdk.git", branch = "Creanova/issue-2228-sdk-settings-schema", subdirectory = "Creanova-tools" }
```

## Using `[tool.uv.sources]` Override

When only `uv` needs the override (keep PyPI versions in the main arrays), add a `[tool.uv.sources]` section. Example from commit `1daca49`:

```toml
[tool.uv.sources]
Creanova-sdk = { git = "https://github.com/Creanova/software-agent-sdk.git", subdirectory = "Creanova-sdk", rev = "4170cca" }
Creanova-agent-server = { git = "https://github.com/Creanova/software-agent-sdk.git", subdirectory = "Creanova-agent-server", rev = "4170cca" }
Creanova-tools = { git = "https://github.com/Creanova/software-agent-sdk.git", subdirectory = "Creanova-tools", rev = "4170cca" }
```

## Released PyPI Version (standard release)

Example from commit `929dcc3` (SDK 1.11.5):

### `dependencies` array

```toml
"Creanova-agent-server==1.11.5",
"Creanova-sdk==1.11.5",
"Creanova-tools==1.11.5",
```

### `[tool.poetry.dependencies]`

```toml
Creanova-sdk = "1.11.5"
Creanova-agent-server = "1.11.5"
Creanova-tools = "1.11.5"
```

### `Creanova/app_server/sandbox/sandbox_spec_service.py`

For released versions, the image tag uses the version number:

```python
AGENT_SERVER_IMAGE = 'ghcr.io/Creanova/agent-server:1.11.5-python'
```

However, **some releases use a commit-hash tag** even for the released version. Check which tag format exists on GHCR. Example from `929dcc3`:

```python
AGENT_SERVER_IMAGE = 'ghcr.io/Creanova/agent-server:010e847-python'
```

## Regenerate Lock Files

After any change to `pyproject.toml`, always regenerate:

```bash
poetry lock
uv lock
cd enterprise && poetry lock && cd ..
```

## CI Guards

- **`check-package-versions.yml`**: Blocks merge to `main` if `[tool.poetry.dependencies]` contains `rev` fields (prevents shipping unreleased SDK pins)
- **`check-version-consistency.yml`**: Validates version strings match across `pyproject.toml`, `package.json`, `package-lock.json`, and verifies compose files use `agent-server` images
