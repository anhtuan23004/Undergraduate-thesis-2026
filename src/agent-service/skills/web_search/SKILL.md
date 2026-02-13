---
name: web_search
description: Search the web for information using curl and process results
tools_allowed: [bash_exec, file_write, file_read]
version: "1.0"
author: "AI Team"
tags: [search, web, information]
---

# Web Search Skill

This skill searches the web for information and processes the results.

## When to Use

Use this skill when the user wants to:
- Find information from the internet
- Search for documentation, tutorials, or articles
- Look up current data or facts

## Instructions

1. **Formulate the search query**
   - Extract key terms from the user request
   - Create a URL-encoded search query

2. **Execute the search**
   - Use `bash_exec` with curl to call a search API or fetch a page
   - Recommended: Use DuckDuckGo HTML or similar
   - Handle rate limits and errors gracefully

3. **Process results**
   - Parse HTML or JSON response
   - Extract relevant information
   - Summarize findings for the user

4. **Save results (optional)**
   - If results are large, use `file_write` to save to a file
   - Provide the file path to the user

## Example Tool Usage

### Search with curl
```
bash_exec {
  "command": "curl -s 'https://duckduckgo.com/html/?q=python+tutorials' | grep -oP '<a[^>]+class="result__a"[^>]+>\K[^<]+' | head -5",
  "timeout": 30
}
```

### Save results to file
```
file_write {
  "path": "./search_results.txt",
  "content": "Search results..."
}
```

## Output Format

Provide a clear summary of findings including:
- Key results found
- Source URLs (if available)
- Brief description of each result
- Any limitations of the search
