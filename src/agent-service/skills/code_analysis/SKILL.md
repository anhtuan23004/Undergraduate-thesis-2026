---
name: code_analysis
description: Analyze code files for quality, bugs, and improvements
tools_allowed: [bash_exec, file_read, file_write]
version: "1.0"
author: "AI Team"
tags: [code, analysis, review, quality]
---

# Code Analysis Skill

Analyze code files for quality issues, potential bugs, and improvement opportunities.

## When to Use

Use this skill when the user wants to:
- Review code quality
- Find potential bugs or issues
- Get suggestions for improvements
- Understand code structure

## Instructions

1. **Read the code files**
   - Use `file_read` to load the target files
   - If directory path provided, use `bash_exec` to list files first

2. **Analyze the code**
   - Check for common issues (syntax errors, unused imports, etc.)
   - Look for code smells (duplication, long functions, etc.)
   - Identify potential bugs or edge cases
   - Check naming conventions and style

3. **Provide recommendations**
   - Prioritize issues by severity (critical, warning, suggestion)
   - Suggest specific code improvements with examples
   - Explain the reasoning behind each suggestion

## Example Tool Usage

### List files in directory
```
bash_exec {
  "command": "find ./src -name '*.py' | head -20"
}
```

### Read a file
```
file_read {
  "path": "./src/main.py",
  "limit": 50
}
```

### Write analysis report
```
file_write {
  "path": "./analysis_report.md",
  "content": "# Code Analysis Report\n\n..."
}
```

## Output Format

Provide structured analysis:

### Summary
- Total files analyzed
- Overall code quality score
- Key findings

### Issues Found
- **Critical**: Bugs or errors that must be fixed
- **Warnings**: Code smells or anti-patterns
- **Suggestions**: Improvements for readability/performance

### Recommendations
- Specific code changes with before/after examples
- Refactoring suggestions
- Best practices to follow
