# Shared Utilities

Common utilities and shared code used across all microservices in the Insurance Claims Processing System.

## Overview

This module contains shared code, utilities, and common configurations that are used by multiple services in the system. Centralizing these components helps maintain consistency and reduces code duplication across the microservices.

## Features

- Common data models and schemas
- Shared utility functions
- Cross-service communication helpers
- Standardized logging configurations
- Common exception classes

## Architecture

```
src/shared/
├── models/           # Shared Pydantic models
├── utils/            # Utility functions
├── exceptions/       # Common exception classes
├── logging/          # Logging utilities
└── constants.py      # Shared constants
```

## Usage

Import shared components in your service:

```python
from shared.models import ClaimData
from shared.utils import format_currency
from shared.exceptions import ValidationError
```

## Development

When adding new shared components:

1. Ensure the component is truly needed by multiple services
2. Keep dependencies minimal to avoid bloating services
3. Document the component's purpose and usage
4. Consider versioning for breaking changes

## Troubleshooting

### Import errors

- Verify the shared module is in the Python path
- Check that the component exists in the expected location
- Ensure no circular dependencies exist
