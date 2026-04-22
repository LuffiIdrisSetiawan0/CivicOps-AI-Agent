# Deployment

The project is deploy-ready as a Dockerized FastAPI app. The repository includes `Dockerfile` and `render.yaml`.

## Render Blueprint

Use the repository's `render.yaml` as the blueprint source. It defines one web service:

```yaml
name: satudata-ops-agent
env: docker
healthCheckPath: /api/health
```

Set these environment variables in Render:

| Variable | Required | Notes |
| --- | --- | --- |
| `OPENAI_API_KEY` | No | Enables chat and polish modes. The app still works without it in fast mode. |
| `OPENAI_MODEL` | Yes | Default in repo: `gpt-5-mini`. |
| `EMBEDDING_MODEL` | Yes | Default in repo: `text-embedding-3-small`. |
| `DATABASE_URL` | Yes | Demo default: `sqlite:///./data/satudata_ops.db`. |
| `CHROMA_PATH` | Yes | Demo default: `./data/chroma`. |

## Production Notes

- Keep `.env` local only; do not commit secrets.
- SQLite is fine for the portfolio demo, but use persistent disk or managed Postgres for longer-running public hosting.
- Add authentication, rate limiting, structured logs, timeouts, and observability before using this as a public production system.

## Smoke Test

After deployment, verify:

```text
GET /api/health
GET /
POST /api/chat
```

