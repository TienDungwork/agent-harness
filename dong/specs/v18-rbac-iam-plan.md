# v18 Plan — IAM RBAC + retrieval rename

## Tasks

| ID | Việc | Done khi |
|----|------|----------|
| 18.1 | Spec + AC-12 + change-log + README index | Spec reviewed |
| 18.2 | IAM client + AccessContext + resolve + FastAPI dep + settings | unit tests mock IAM |
| 18.3 | role_matrix + domain guard + schema table filter | SECURITY vs ENV cases |
| 18.4 | `apply_access_scope` geo + tests | inject org/site/area/zone |
| 18.5 | Docs retrieval filter by domain | cards ngoài domain bị loại |
| 18.6 | Rename knowledge → retrieval | imports xanh |
| 18.7 | FE headers + smoke checklist | Bearer + X-Organization-Id |

## Files

- New: `infra/auth/iam_client.py`, `domain/authz/{access_context,role_matrix,resolve,domain_guard}.py`; glue `api/helpers/auth.get_access_context`
- Edit: settings, routes_agent, agent_turn, state, scope.py, plan/supervisor, frontend, retrieval packages
