# Langflow Example Flows

This directory contains example flows for insurance claims processing.

## Available Flows

### 1. Simple Claim Triage

A basic flow that classifies claims by urgency based on amount and diagnosis.

**How to import:**
1. Open Langflow UI at http://localhost:7860
2. Click **New Project**
3. Click **Import** (upload the JSON file)
4. Or copy-paste the JSON into the import dialog

### 2. Policy Q&A

A flow that answers questions about insurance policies using the RAG service.

### 3. Document Classifier

Routes documents to appropriate processors based on content type.

## Creating Your Own Flows

1. Start with a template from this directory
2. Import into Langflow
3. Customize components for your use case
4. Test in the Playground
5. Export and save to this directory for version control

## Flow Structure

Each flow JSON contains:
- **Nodes**: Components (LLMs, tools, logic)
- **Edges**: Connections between nodes
- **Parameters**: Configuration for each component

Example structure:
```json
{
  "name": "My Flow",
  "description": "Description of what this flow does",
  "nodes": [...],
  "edges": [...]
}
```
