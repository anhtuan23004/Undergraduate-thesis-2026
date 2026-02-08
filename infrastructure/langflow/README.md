# Langflow - Visual Business Flow Designer

Langflow is a visual tool for building AI workflows and agents using a drag-and-drop interface.

## What is Langflow?

Langflow allows you to:
- **Design flows visually** - Drag and drop components to create workflows
- **Test interactively** - Debug and run flows directly in the UI
- **Export to API** - Deploy flows as REST endpoints
- **Extend with custom components** - Build insurance-specific components

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LANGFLOW DESIGNER                        │
│  - Visual flow design (localhost:7860)                      │
│  - Component library (LLMs, tools, logic)                   │
│  - Testing and debugging                                    │
│  - Export to JSON / Python / API                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    YOUR APPLICATION                         │
│  - Import designed flows                                    │
│  - Run with LangGraph runtime                               │
│  - Integrate with existing services                         │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Start Langflow

```bash
cd infrastructure/langflow

# Create the shared network if not exists
docker network create backend 2>/dev/null || true

# Start Langflow
docker-compose -f docker-compose.langflow.yml up -d
```

### 2. Access the UI

Open http://localhost:7860 in your browser.

**Default credentials:**
- Username: `admin`
- Password: `admin123`

### 3. Create Your First Flow

1. Click **New Project**
2. Drag components from the sidebar:
   - **Chat Input** → **OpenAI** → **Chat Output**
3. Configure the OpenAI component with your API key
4. Click **Playground** to test
5. Save and export

## Useful Flows for Insurance Claims

### 1. Document Classification Flow

```
[Document Text] → [Classifier LLM] → [Router]
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
          ▼                           ▼                           ▼
   [Invoice Processor]      [Medical Record Parser]      [Policy Validator]
```

**Purpose:** Automatically classify incoming documents and route to appropriate processor.

### 2. Claim Decision Support Flow

```
[Claim Data] → [Policy Check] → [ICD Lookup] → [Coverage Calc] → [Decision]
                   │                │                │              │
                   └────────────────┴────────────────┘              │
                                    │                               │
                                    ▼                               ▼
                              [Risk Scorer]                  [Final Output]
```

**Purpose:** Assist adjusters with AI-powered decision recommendations.

### 3. Fraud Detection Flow

```
[Claim] → [Amount Check] ─┬─→ [Duplicate Detection] ─┐
                          │                           │
                          └─→ [Velocity Check] ──────┼─→ [Risk Aggregator] → [Alert/Pass]
                          │                           │
                          └─→ [Pattern Matching] ─────┘
```

**Purpose:** Parallel fraud checks with aggregated risk scoring.

## Custom Components

Custom components for insurance domain are in `./custom-components/`:

| Component | Description | Usage |
|-----------|-------------|-------|
| `ICDLookup` | Validate ICD-10 diagnosis codes | Medical claim validation |
| `PolicyChecker` | Query policy coverage from RAG service | Coverage verification |
| `CoverageCalculator` | Calculate eligible amounts | Amount computation |
| `DocumentClassifier` | Classify document types | Document routing |

### Using Custom Components

1. Components are auto-loaded from `/app/custom-components` in the container
2. In Langflow UI, look for components under **Custom** category
3. Drag and configure like any other component

## Integration with Existing Services

### Call RAG Service from Flow

Use an **API Request** component:
- Method: `POST`
- URL: `http://rag-service:8000/api/v1/rag/query`
- Body: `{"query": "{input}", "policy_number": "POL-001"}`

### Call Agent Service from Flow

Use an **API Request** component:
- Method: `POST`
- URL: `http://agent-service:8000/api/v1/agent/decide`
- Body: JSON with claim data

### Export and Use in Code

1. Design flow in Langflow
2. Click **Export** → **Download JSON**
3. Load in your application:

```python
from langflow.load import load_flow

flow = load_flow("my-flow.json")
result = flow.run({"input": "claim data"})
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LANGFLOW_PORT` | Port for Langflow UI | 7860 |
| `LANGFLOW_SECRET_KEY` | Secret for encryption | changeme... |
| `LANGFLOW_AUTO_LOGIN` | Skip login screen | true |
| `LANGFLOW_SUPERUSER` | Admin username | admin |
| `LANGFLOW_SUPERUSER_PASSWORD` | Admin password | admin123 |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `GEMINI_API_KEY` | Gemini API key | - |

## Commands

```bash
# Start Langflow
docker-compose -f docker-compose.langflow.yml up -d

# View logs
docker-compose -f docker-compose.langflow.yml logs -f

# Stop Langflow
docker-compose -f docker-compose.langflow.yml down

# Reset data (WARNING: deletes all flows!)
docker-compose -f docker-compose.langflow.yml down -v
```

## Workflow: Design → Test → Deploy

### Step 1: Design in Langflow
1. Open http://localhost:7860
2. Create new project
3. Build flow using visual editor
4. Test in Playground

### Step 2: Export Flow
- **Option A:** Export as JSON → import in code
- **Option B:** Export as Python → customize and deploy
- **Option C:** Deploy as API endpoint within Langflow

### Step 3: Integrate

**If exporting to Agent Service:**
```python
# In your service
from langflow.load import load_flow

class FlowBasedProcessor:
    def __init__(self):
        self.flow = load_flow("/path/to/exported-flow.json")

    async def process(self, data):
        return await self.flow.arun(data)
```

## Comparison: Langflow vs LangGraph

| Feature | Langflow | LangGraph (Current) |
|---------|----------|---------------------|
| Design | Visual drag-and-drop | Code-based |
| Learning Curve | Low | Medium |
| Flexibility | Good | Excellent |
| Version Control | JSON exports | Git native |
| Debugging | Visual step-through | Logs/traces |
| Best For | Business analysts, prototyping | Developers, production |

**Recommendation:** Use Langflow for designing and prototyping flows, then export to LangGraph for production deployment.

## Troubleshooting

### Langflow won't start
```bash
# Check logs
docker-compose -f docker-compose.langflow.yml logs langflow

# Check database is healthy
docker-compose -f docker-compose.langflow.yml ps
```

### Components not loading
- Ensure custom component files are valid Python
- Check component class extends `CustomComponent`
- Verify component is in `./custom-components/` directory

### API calls to other services fail
- Ensure all services are on the same Docker network (`backend`)
- Use service names as hostnames (e.g., `rag-service`, not `localhost`)
- Check service is running: `docker-compose ps`

## Resources

- [Langflow Documentation](https://docs.langflow.org/)
- [Langflow GitHub](https://github.com/langflow-ai/langflow)
- [Component Reference](https://docs.langflow.org/components)
- [API Export Guide](https://docs.langflow.org/workspace-api)
