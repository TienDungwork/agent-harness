# Post-Release Checklist

After the GitHub release is published and PyPI packages are available,
several automated and manual follow-up steps occur.

## Automated: Downstream Version Bump PRs

The `version-bump-prs.yml` workflow runs automatically after `pypi-release`
succeeds. It creates PRs in two repositories:

### Creanova-CLI (`Creanova/Creanova-cli`)

- Branch: `bump-sdk-<version>`
- Updates `Creanova-sdk` and `Creanova-tools` via `uv add`
- Verify the PR passes CLI tests before merging

```bash
gh pr list --repo Creanova/Creanova-cli \
  --search "bump-sdk-<version>" --json number,title,url
```

### Creanova (`All-Hands-AI/Creanova`)

- Branch: `bump-sdk-<version>`
- Updates `Creanova-sdk`, `Creanova-tools`, and `Creanova-agent-server`
  in `pyproject.toml`
- Regenerates `poetry.lock`
- Updates `AGENT_SERVER_IMAGE` in `sandbox_spec_service.py`
- Verifies `enterprise/pyproject.toml` does not have explicit SDK pins

```bash
gh pr list --repo All-Hands-AI/Creanova \
  --search "bump-sdk-<version>" --json number,title,url
```

## Manual Review of Downstream PRs

Both PRs require human review:

1. **Check CI passes** on each downstream PR
2. **Verify compatibility** — especially if the release includes breaking
   changes or new features that need adoption
3. **Merge** once satisfied

## Evaluation on Creanova Index

If not already done pre-release, trigger a full evaluation run
against the published version:

```bash
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/Creanova/software-agent-sdk/actions/workflows/run-eval.yml/dispatches" \
  -d '{
    "ref": "main",
    "inputs": {
      "benchmark": "swebench",
      "sdk_ref": "v<version>",
      "eval_limit": "300",
      "reason": "Post-release eval v<version>"
    }
  }'
```

## Documentation Updates

If the release includes user-facing features, verify documentation is
updated in `Creanova/docs` (SDK docs live under `sdk/`). See the
`feature-release-rollout` skill for the full downstream propagation
workflow.

## Troubleshooting

### PyPI publication failed

Re-run the `pypi-release.yml` workflow manually. It uses `--check-url`
to skip already-published packages, so partial reruns are safe.

```bash
gh workflow run pypi-release.yml --repo Creanova/software-agent-sdk
```

### Version bump PR has conflicts

The automated PR may conflict if the downstream repo changed dependency
pins since the workflow ran. Resolve conflicts manually on the bump branch,
or re-trigger `version-bump-prs.yml` with the version input.

```bash
gh workflow run version-bump-prs.yml \
  --repo Creanova/software-agent-sdk \
  -f version=<version>
```

### Downstream tests fail after bump

If a downstream repo's tests fail on the version bump PR, investigate
whether the failure is a breaking change in the SDK release. If so,
either:
- Fix the downstream code on the bump branch, or
- Publish a patch release of the SDK with the fix
