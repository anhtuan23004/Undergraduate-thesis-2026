# MongoDB Infrastructure

MongoDB 7.0.4 for document storage and agent memory.

## Services

| Service | Port | Description |
|---------|------|-------------|
| MongoDB | 27017 | Main database |
| Mongo Express | 8081 | Web UI for MongoDB |

## Default Credentials

```yaml
Root Username: admin
Root Password: admin123
App Username: claims_app
App Password: claims_password
Database: claims
```

## Collections

- `agent_sessions` - Agent conversation history
- `documents` - Processed document metadata
- `extractions` - OCR extraction results
- `audit_logs` - Decision audit trail
- `workflows` - Workflow execution state
- `agent_checkpoints` - LangGraph state persistence

## Quick Start

```bash
docker-compose -f infrastructure/mongodb/docker-compose.yml up -d
```

## Access

```bash
# MongoDB shell
docker exec -it claims-mongodb mongosh -u admin -p admin123

# Mongo Express (Web UI)
open http://localhost:8081
```
