# Langfuse Self-Hosted Setup

This directory contains the Docker Compose configuration for self-hosting Langfuse locally.

## Services

| Service | Description | Port |
|---------|-------------|------|
| langfuse-web | Main Langfuse UI | 3000 |
| langfuse-worker | Background job processor | 3030 (localhost only) |
| clickhouse | Analytics database | 18123 (HTTP), 19000 (native) |
| minio | S3-compatible storage | 9090 (API), 9091 (console) |
| redis | Cache and queues | 16379 |
| postgres | Main database | 15432 |

## Quick Start

1. **Start Langfuse:**
   ```bash
   cd infrastructure/langfuse
   docker-compose -f docker-compose.langfuse.yml up -d
   ```

2. **Wait for services to be ready** (first startup takes ~30-60 seconds)

3. **Access Langfuse:**
   - UI: http://localhost:3000
   - MinIO Console: http://localhost:9091 (login: minio / miniosecret)

4. **Create your account:**
   - Open http://localhost:3000
   - Sign up with your email
   - Create an organization and project
   - Get your API keys from Settings → API Keys

## Configuration

Edit the `.env` file to customize:

- `NEXTAUTH_SECRET` - Change for production (min 32 chars)
- `ENCRYPTION_KEY` - Already generated, but change for production
- `SALT` - Already generated
- Initial user/project setup (optional)

### Optional: Auto-create Organization/Project

Uncomment and set these in `.env`:
```bash
LANGFUSE_INIT_ORG_ID=my-org
LANGFUSE_INIT_ORG_NAME="My Organization"
LANGFUSE_INIT_PROJECT_ID=my-project
LANGFUSE_INIT_PROJECT_NAME="My Project"
LANGFUSE_INIT_USER_EMAIL=admin@example.com
LANGFUSE_INIT_USER_NAME="Admin User"
LANGFUSE_INIT_USER_PASSWORD=securepassword123
```

## Connecting Your Application

Once Langfuse is running, configure your application services:

```bash
# Add to your main .env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=http://localhost:3000
```

### Python SDK Example

```python
from langfuse import Langfuse

langfuse = Langfuse(
    public_key="pk-lf-...",
    secret_key="sk-lf-...",
    host="http://localhost:3000"
)

# Trace your LLM calls
with langfuse.trace(name="claim-processing") as trace:
    # Your code here
    trace.generation(name="llm-call", model="gpt-4", ...)
```

## Useful Commands

```bash
# Start Langfuse
docker-compose -f docker-compose.langfuse.yml up -d

# View logs
docker-compose -f docker-compose.langfuse.yml logs -f

# Stop Langfuse
docker-compose -f docker-compose.langfuse.yml down

# Reset data (WARNING: deletes all data!)
docker-compose -f docker-compose.langfuse.yml down -v
```

## Data Persistence

Data is stored in Docker volumes:
- `langfuse_postgres_data` - Main database
- `langfuse_clickhouse_data` - Analytics data
- `langfuse_minio_data` - File uploads

## Troubleshooting

### Port Conflicts
The compose file uses non-standard ports to avoid conflicts with the main infrastructure:
- Postgres: 15432 (instead of 5432)
- Redis: 16379 (instead of 6379)
- ClickHouse: 18123, 19000
- MinIO: 9090, 9091 (main infra uses 9000, 9001)

### Services Not Starting
Check health status:
```bash
docker-compose -f docker-compose.langfuse.yml ps
```

View specific service logs:
```bash
docker-compose -f docker-compose.langfuse.yml logs postgres
docker-compose -f docker-compose.langfuse.yml logs clickhouse
```

## References

- [Langfuse Docs](https://langfuse.com/docs)
- [Self-Hosting Guide](https://langfuse.com/docs/deployment/self-host)
- [Docker Compose Original](https://github.com/langfuse/langfuse/blob/main/docker-compose.yml)
