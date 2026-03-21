
# Medication Repository

This directory contains the medication database and related data files used by the insurance claims processing system.

## Overview

The medication repository serves as a centralized source of truth for medication validation and reference within the AI agent's decision-making pipeline.

## Contents

- **Medication Database** - Comprehensive medication records with properties (name, category, active ingredients, contraindications)
- **Reference Data** - Supporting data for validation (dosages, interactions, formulations)
- **Sample Documents** - Example insurance claim documents for testing and development

## Integration Points

- **Agent Service** (`src/agent-service`) - Uses `search_medicine` tool to validate medications in claims
- **MongoDB** - Persists medication records for rapid lookup

## Usage

Medications are automatically loaded during service startup. Use the Agent service's `/api/v2/process` endpoint with claim documents containing medication information.
