# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0-alpha.2] - 2025-05-11

### Added

- Initial npm package release of `@Creanova/agent-canvas`
- CLI entry point (`npx @Creanova/agent-canvas`) to run full stack locally
- Library build mode with component barrel exports
- Subpath exports for modular imports:
  - `@Creanova/agent-canvas/browser`
  - `@Creanova/agent-canvas/conversation`
  - `@Creanova/agent-canvas/files`
  - `@Creanova/agent-canvas/settings`
  - `@Creanova/agent-canvas/sidebar`
  - `@Creanova/agent-canvas/terminal`
  - `@Creanova/agent-canvas/i18n`
- TypeScript type declarations
- GitHub Actions workflow for automated npm publishing (OIDC trusted publishing)

[Unreleased]: https://github.com/Creanova/agent-canvas/compare/v1.0.0-alpha.2...HEAD
[1.0.0-alpha.2]: https://github.com/Creanova/agent-canvas/releases/tag/v1.0.0-alpha.2
