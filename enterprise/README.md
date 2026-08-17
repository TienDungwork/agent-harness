# Creanova Enterprise Server
> [!WARNING]
> This software is licensed under the [Polyform Free Trial License](./LICENSE). This is **NOT** an open source license. Usage is limited to 30 days per calendar year without a commercial license. If you would like to use it beyond 30 days, please [contact us](https://www.Creanova.dev/contact).

> [!WARNING]
> This is a work in progress and may contain bugs, incomplete features, or breaking changes.

This directory contains the enterprise server used by [Creanova Cloud](https://github.com/All-Hands-AI/Creanova-Cloud/). The official, public version of Creanova Cloud is available at
[app.all-hands.dev](https://app.all-hands.dev).

You may also want to check out the MIT-licensed [Creanova](https://github.com/Creanova/Creanova)

## Extension of Creanova

The code in `/enterprise` builds on top of Creanova (MIT-licensed), extending its functionality. The enterprise code is entangled with Creanova in two ways:

- Enterprise stacks on top of Creanova. For example, the middleware in enterprise is stacked right on top of the middlewares in Creanova. In `SAAS`, the middleware from BOTH repos will be present and running (which can sometimes cause conflicts)

- Enterprise overrides the implementation in Creanova (only one is present at a time). For example, the server config SaasServerConfig overrides [`ServerConfig`](https://github.com/Creanova/Creanova/blob/main/Creanova/server/config/server_config.py#L8) in Creanova. This is done through dynamic imports ([see here](https://github.com/Creanova/Creanova/blob/main/Creanova/server/config/server_config.py#L37-#L45))

Key areas that change on `SAAS` are

- Authentication
- User settings
- etc

### Authentication

| Aspect                    | Creanova                                              | Enterprise                                                                                                                                 |
| ------------------------- | ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Authentication Method** | User adds a personal access token (PAT) through the UI | User performs OAuth through the UI. The GitHub app provides a short-lived access token and refresh token                            |
| **Token Storage**         | PAT is stored in **Settings**                          | Token is stored in **GithubTokenManager** (a file store in our backend)                                                             |
| **Authenticated status**  | We simply check if token exists in `Settings`          | We issue a signed cookie with `github_user_id` during OAuth, so subsequent requests with the cookie can be considered authenticated |

Note that in the future, authentication will happen via keycloak. All modifications for authentication will happen in enterprise.

### GitHub Service

The github service is responsible for interacting with Github APIs. As a consequence, it uses the user's token and refreshes it if need be

| Aspect                    | Creanova                               | Enterprise                                            |
| ------------------------- | -------------------------------------- | ---------------------------------------------- |
| **Class used**            | `GitHubService`                        | `SaaSGitHubService`                            |
| **Token used**            | User's PAT fetched from `Settings`     | User's token fetched from `GitHubTokenManager` |
| **Refresh functionality** | **N/A**; user provides PAT for the app | Uses the `GitHubTokenManager` to refresh       |

NOTE: in the future we will simply replace the `GithubTokenManager` with keycloak. The `SaaSGithubService` should interact with keycloack instead.

### Email delivery (SMTP for invitations & budget alerts)

Organization invitation emails and budget alert emails are sent via SMTP when configured. If
`SMTP_HOST` is unset, invitations are still created but no email is sent (the UI surfaces
copyable invite links instead).

| Env var | Purpose | Default |
| --- | --- | --- |
| `SMTP_HOST` | SMTP server hostname | (required) |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_USERNAME` | SMTP auth username | empty |
| `SMTP_PASSWORD` | SMTP auth password | empty |
| `SMTP_FROM_EMAIL` | Sender address | `Creanova <no-reply@Creanova.dev>` |
| `SMTP_USE_SSL` | Use implicit TLS/SSL | `false` |
| `SMTP_USE_TLS` | StartTLS upgrade (ignored if SSL) | `true` |


# Areas that are BRITTLE!

## User ID vs User Token

- In Creanova, the entire app revolves around the GitHub token the user sets. `Creanova/server` uses `request.state.github_token` for the entire app
- On Enterprise, the entire APP resolves around the Github User ID. This is because the cookie sets it, so `Creanova/server` AND `enterprise/server` depend on it and completely ignore `request.state.github_token` (token is fetched from `GithubTokenManager` instead)

Note that introducing GitHub User ID in Creanova, for instance, will cause large breakages.
