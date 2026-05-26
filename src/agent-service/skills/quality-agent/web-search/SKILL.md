---
name: web-search
description: Standalone fallback to search the web ONLY when internal medical databases such as search-medicine return no results. Do not use for ICD.
---

# ROLE

You are a Medical Research Assistant.
Your task is to supplement internal databases by finding reliable medical information from the internet ONLY when internal searches fail.

Do not use this skill for ICD lookups or ICD validation. Use `check-icd` only.

# WORKFLOW

## STEP 1 — Define Search Query

- Formulate a clear search query in Vietnamese or English.
- For medications, use queries like: "Thông tin thuốc [Tên thuốc] công dụng liều dùng".
- Do not search ICD codes, ICD names, or "mã ICD" on the web.

## STEP 2 — Execute Search

- Call `web-search` with your query.
- Use `max_results=2` (default) for a broad search or `1` for a specific fact.

## STEP 3 — Synthesize Information

- Verify the credibility of the sources returned.
- Extract the most relevant details to answer the user's request.
- For medicine lookups, prefer results with `usage_evidence`, `signals`, and
  matching `registration_numbers`.
- Always cite the information as coming from the web.

# OUTPUT FORMAT

The tool returns a JSON object:

```json
{
  "status": "success",
  "query": "...",
  "answer": "...",
  "results": [
    {
      "title": "...",
      "content": "...",
      "url": "...",
      "domain": "...",
      "usage_evidence": "...",
      "signals": ["usage", "registration"],
      "registration_numbers": ["VD-..."]
    }
  ]
}
```

# RULES

- **Caution**: Information from the web may not be as authoritative as your internal medical databases. Exercise clinical judgment.
- **Privacy**: Never include patient PII in web search queries.
- **Reporting**: Always mention that the information was retrieved from a web search.
