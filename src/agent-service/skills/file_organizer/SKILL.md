---
name: file_organizer
description: Organize files by type, date, or custom rules
tools_allowed: [bash_exec, file_read, file_write]
version: "1.0"
author: "AI Team"
tags: [files, organization, automation]
---

# File Organizer Skill

Organize files in directories by type, date, or custom rules.

## When to Use

Use this skill when the user wants to:
- Clean up messy directories
- Organize files by type (images, documents, etc.)
- Sort files by date
- Apply custom organization rules

## Instructions

1. **Analyze the directory**
   - Use `bash_exec` to list files and get information
   - Identify file types, sizes, and dates
   - Understand current structure

2. **Plan organization strategy**
   - Determine categorization approach (by type, date, etc.)
   - Plan directory structure
   - Identify any conflicts or special cases

3. **Execute organization**
   - Use bash commands to create directories
   - Move/copy files to appropriate locations
   - Handle naming conflicts

4. **Verify results**
   - Check that all files are organized
   - Verify no files were lost
   - Report the new structure

## Example Tool Usage

### List files with details
```
bash_exec {
  "command": "ls -la ./downloads/ | awk '{print $9, $6, $7, $8}'"
}
```

### Create directory structure
```
bash_exec {
  "command": "mkdir -p ./organized/{images,documents,videos,others}"
}
```

### Move files by type
```
bash_exec {
  "command": "mv ./downloads/*.{jpg,jpeg,png,gif} ./organized/images/ 2>/dev/null || true"
}
```

## Output Format

Provide a summary of actions:
- Original file count
- Organization strategy used
- New directory structure
- Files moved by category
- Any issues encountered
