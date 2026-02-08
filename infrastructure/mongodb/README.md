# MongoDB Infrastructure

MongoDB 7.0.4 for document storage and agent memory persistence.

## Overview

This module provides MongoDB infrastructure for the Insurance Claims Processing System. MongoDB serves as the primary document database for storing claim data, agent conversation history, document metadata, and LangGraph state checkpoints.

## Features

- Document storage for claim data and metadata
- Agent session persistence
- OCR extraction result storage
- Audit logging for claim decisions
- LangGraph state checkpointing
- Web UI for database management (Mongo Express)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      MongoDB 7.0.4                           │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   claims     │  │a │  │  (metadgent_sessions│  │  documents   │      │
│  │   (main)     │  │  (history)  ata)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ extractions  │  │  audit_logs  │  │  workflows   │      │
│  │   (OCR)      │  │  (decisions) │  │   (state)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────┐                                           │
│  │agent_checkpts│  (LangGraph persistence)                  │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Mongo Express   │
                    │    (Web UI)      │
                    │     :8081        │
                    └──────────────────┘
```

## Quick Start

Start MongoDB and Mongo Express:

```bash
docker-compose -f infrastructure/mongodb/docker-compose.yml up -d
```

Or start via main compose file:

```bash
docker-compose up -d mongodb mongo-express
```

## Configuration

### Default Credentials

| Role | Username | Password | Database |
|------|----------|----------|----------|
| Root | `admin` | `admin123` | admin |
| Application | `claims_app` | `claims_password` | claims |

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGO_INITDB_ROOT_USERNAME` | Root username | `admin` |
| `MONGO_INITDB_ROOT_PASSWORD` | Root password | `admin123` |
| `MONGO_APP_USERNAME` | Application username | `claims_app` |
| `MONGO_APP_PASSWORD` | Application password | `claims_password` |
| `MONGO_APP_DATABASE` | Application database | `claims` |

## Collections

| Collection | Purpose |
|------------|---------|
| `agent_sessions` | Agent conversation history |
| `documents` | Processed document metadata |
| `extractions` | OCR extraction results |
| `audit_logs` | Decision audit trail |
| `workflows` | Workflow execution state |
| `agent_checkpoints` | LangGraph state persistence |

## Usage

### MongoDB Shell Access

```bash
# Connect to MongoDB shell
docker exec -it claims-mongodb mongosh -u admin -p admin123

# Use claims database
use claims

# List collections
show collections

# Query documents
db.documents.find().limit(5)
```

### Mongo Express Web UI

Access the web UI at: http://localhost:8081

Default credentials:
- Username: `admin`
- Password: `pass`

### Application Connection

Connection string for applications:
```
mongodb://claims_app:claims_password@localhost:27017/claims
```

## Development

### Backup and Restore

```bash
# Backup database
docker exec claims-mongodb mongodump -u admin -p admin123 --out /backup

# Restore database
docker exec claims-mongodb mongorestore -u admin -p admin123 /backup
```

### Reset Database

```bash
# Stop and remove container with volume
docker-compose -f infrastructure/mongodb/docker-compose.yml down -v

# Start fresh
docker-compose -f infrastructure/mongodb/docker-compose.yml up -d
```

## Troubleshooting

### Connection refused

- Verify MongoDB container is running: `docker-compose ps mongodb`
- Check port 27017 is not in use by another process
- Review logs: `docker-compose logs mongodb`

### Authentication failed

- Verify credentials in connection string
- Check that init scripts ran successfully
- Reset container if needed: `docker-compose down -v && docker-compose up -d`

### Mongo Express not accessible

- Verify Mongo Express container is running
- Check port 8081 is not in use
- Ensure MongoDB is fully started before Mongo Express
