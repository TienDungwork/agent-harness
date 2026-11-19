# Prompts (code)

| llm-engineer-demo | dong |
|-------------------|------|
| LangSmith Hub definitions/push | Git YAML `resource/prompts/<name>/vN.yaml` + `production.txt` |
| `app/prompts/registry.py` | `src/infra/prompts/registry.py` |
| `app/prompts/lint.py` | `src/infra/prompts/lint.py` |
| A/B sticky | `experiment.py` — `run_agent` gọi `resolve_prompt_version(user_id)`; `PROMPT_AB_*` trong `.env` |

`production.txt` **chỉ** chứa version (`v1`), không chứa full template.

Lint:

```bash
PYTHONPATH=. python -m src.infra.prompts.lint
```
