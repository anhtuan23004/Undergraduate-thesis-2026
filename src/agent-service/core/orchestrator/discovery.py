"""Skill discovery - scans ./skills/ directory and parses SKILL.md files.

Each skill is a directory containing:
- SKILL.md: Markdown file with YAML frontmatter containing metadata
- Optional: scripts, resources, or other files used by the skill

Example SKILL.md:
---
name: web_search
description: Search the web for information
tools_allowed: [bash_exec, file_write]
version: "1.0"
author: "AI Team"
tags: [search, web]
---

# Web Search Skill

Use this skill to search the web for information.

## Instructions

1. Formulate a search query based on user input
2. Use bash_exec to run a search command
3. Process and summarize results

## Tools Available

- `bash_exec`: Execute shell commands
- `file_write`: Write results to file
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

import structlog
import yaml

from core.orchestrator.models import SkillInfo

logger = structlog.get_logger()


class SkillDiscovery:
    """Discovers and loads skills from the skills directory.

    Scans the ./skills/ directory for subdirectories containing SKILL.md files.
    Parses YAML frontmatter to extract skill metadata.
    """

    def __init__(self, skills_dir: str = "./skills"):
        """Initialize the skill discovery.

        Args:
            skills_dir: Path to the skills directory (relative or absolute)
        """
        self.skills_dir = Path(skills_dir).resolve()
        self._skills_cache: Dict[str, SkillInfo] = {}
        self.logger = logger.bind(component="skill_discovery")

    def discover_all(self) -> List[SkillInfo]:
        """Discover all skills in the skills directory.

        Returns:
            List of discovered SkillInfo objects
        """
        skills = []

        if not self.skills_dir.exists():
            self.logger.warning(
                "Skills directory does not exist",
                path=str(self.skills_dir)
            )
            return skills

        # Scan subdirectories
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                try:
                    skill = self._parse_skill_file(skill_dir, skill_file)
                    skills.append(skill)
                    self._skills_cache[skill.name] = skill
                    self.logger.debug(
                        "Discovered skill",
                        name=skill.name,
                        path=str(skill_dir)
                    )
                except Exception as e:
                    self.logger.error(
                        "Failed to parse skill file",
                        path=str(skill_file),
                        error=str(e)
                    )

        self.logger.info(
            "Skill discovery complete",
            count=len(skills),
            path=str(self.skills_dir)
        )
        return skills

    def get_skill(self, name: str) -> Optional[SkillInfo]:
        """Get a skill by name.

        Args:
            name: Skill name

        Returns:
            SkillInfo if found, None otherwise
        """
        # Check cache first
        if name in self._skills_cache:
            return self._skills_cache[name]

        # Try to discover if not in cache
        if not self._skills_cache:
            self.discover_all()

        return self._skills_cache.get(name)

    def find_by_tag(self, tag: str) -> List[SkillInfo]:
        """Find skills by tag.

        Args:
            tag: Tag to search for

        Returns:
            List of matching skills
        """
        if not self._skills_cache:
            self.discover_all()

        return [
            skill for skill in self._skills_cache.values()
            if tag in skill.tags
        ]

    def _parse_skill_file(self, skill_dir: Path, skill_file: Path) -> SkillInfo:
        """Parse a SKILL.md file.

        Args:
            skill_dir: Path to skill directory
            skill_file: Path to SKILL.md file

        Returns:
            Parsed SkillInfo

        Raises:
            ValueError: If parsing fails
        """
        content = skill_file.read_text(encoding="utf-8")

        # Parse YAML frontmatter and markdown body
        frontmatter, body = self._split_frontmatter(content)

        # Parse YAML
        try:
            metadata = yaml.safe_load(frontmatter) if frontmatter else {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML frontmatter: {e}")

        # Validate required fields
        if "name" not in metadata:
            # Use directory name as fallback
            metadata["name"] = skill_dir.name

        if "description" not in metadata:
            raise ValueError(f"Skill {metadata['name']} missing required 'description' field")

        # Build SkillInfo
        return SkillInfo(
            name=metadata["name"],
            description=metadata["description"],
            path=str(skill_dir),
            tools_allowed=metadata.get("tools_allowed", []),
            version=str(metadata.get("version", "1.0")),
            author=metadata.get("author"),
            tags=metadata.get("tags", []),
            instructions=body.strip()
        )

    @staticmethod
    def _split_frontmatter(content: str) -> tuple:
        """Split YAML frontmatter from markdown body.

        Expected format:
        ---
        key: value
        ---
        # Markdown content

        Args:
            content: Full file content

        Returns:
            Tuple of (frontmatter_yaml, body_markdown)
        """
        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)

        if match:
            return match.group(1), match.group(2)

        # No frontmatter found, return empty frontmatter and full content
        return "", content

    def reload(self) -> List[SkillInfo]:
        """Reload all skills (clear cache and rediscover).

        Returns:
            List of discovered skills
        """
        self._skills_cache.clear()
        return self.discover_all()
