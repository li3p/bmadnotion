"""Configuration management for bmadnotion."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ConfigNotFoundError(Exception):
    """Raised when configuration file is not found."""

    pass


class TokenNotFoundError(Exception):
    """Raised when Notion token is not found in environment."""

    pass


class DocumentConfig(BaseModel):
    """Configuration for a document to sync."""

    path: str
    title: str


class NotionConfig(BaseModel):
    """Notion API configuration."""

    token_env: str = "NOTION_TOKEN"
    workspace_page_id: str


class PathsConfig(BaseModel):
    """Paths configuration."""

    bmad_output: Path = Path("_bmad-output")
    planning_artifacts: Path = Path("_bmad-output/planning-artifacts")
    implementation_artifacts: Path = Path("_bmad-output/implementation-artifacts")
    epics_dir: Path = Path("_bmad-output/planning-artifacts/epics")
    sprint_status: Path = Path("_bmad-output/implementation-artifacts/sprint-status.yaml")


class SprintsDbConfig(BaseModel):
    """Sprints database configuration."""

    database_id: str | None = None
    key_property: str = "BMADEpic"
    status_mapping: dict[str, str] = Field(default_factory=lambda: {
        "backlog": "Not Started",
        "in-progress": "In Progress",
        "done": "Done",
    })


class TasksDbConfig(BaseModel):
    """Tasks database configuration."""

    database_id: str | None = None
    key_property: str = "BMADStory"
    status_mapping: dict[str, str] = Field(default_factory=lambda: {
        "backlog": "Backlog",
        "ready-for-dev": "Ready",
        "in-progress": "In Progress",
        "review": "Review",
        "done": "Done",
    })


class ProjectsDbConfig(BaseModel):
    """Projects database configuration."""

    database_id: str | None = None
    key_property: str = "BMADProject"
    name_property: str = "Project name"


class PageSyncConfig(BaseModel):
    """Page sync configuration."""

    enabled: bool = True
    parent_page_id: str | None = None
    documents: list[DocumentConfig] = Field(default_factory=list)


class DatabaseSyncConfig(BaseModel):
    """Database sync configuration."""

    enabled: bool = True
    projects: ProjectsDbConfig = Field(default_factory=ProjectsDbConfig)
    sprints: SprintsDbConfig = Field(default_factory=SprintsDbConfig)
    tasks: TasksDbConfig = Field(default_factory=TasksDbConfig)


class Config(BaseModel):
    """Main configuration model."""

    project: str
    notion: NotionConfig
    paths: PathsConfig = Field(default_factory=PathsConfig)
    page_sync: PageSyncConfig = Field(default_factory=PageSyncConfig)
    database_sync: DatabaseSyncConfig = Field(default_factory=DatabaseSyncConfig)

    # Internal: project root path (not from config file)
    _project_root: Path | None = None

    def get_notion_token(self) -> str:
        """Get Notion token from environment variable.

        Raises:
            TokenNotFoundError: If the environment variable is not set.
        """
        token = os.environ.get(self.notion.token_env)
        if not token:
            raise TokenNotFoundError(
                f"Notion token not found. Set the {self.notion.token_env} environment variable."
            )
        return token


def _resolve_paths(config: Config, project_root: Path) -> Config:
    """Resolve relative paths to absolute paths."""
    paths_dict = config.paths.model_dump()

    for key, value in paths_dict.items():
        if isinstance(value, Path) and not value.is_absolute():
            paths_dict[key] = project_root / value

    config.paths = PathsConfig(**paths_dict)
    config._project_root = project_root
    return config


def _discover_bmad_paths(project_root: Path) -> dict[str, Any]:
    """Discover paths from _bmad/bmm/config.yaml if it exists."""
    bmad_config_path = project_root / "_bmad" / "bmm" / "config.yaml"

    if not bmad_config_path.exists():
        return {}

    with open(bmad_config_path) as f:
        bmad_config = yaml.safe_load(f) or {}

    paths = {}

    # Map BMAD config keys to our config keys
    key_mapping = {
        "output_folder": "bmad_output",
        "planning_artifacts": "planning_artifacts",
        "implementation_artifacts": "implementation_artifacts",
    }

    for bmad_key, our_key in key_mapping.items():
        if bmad_key in bmad_config:
            # Replace {project-root} placeholder
            value = bmad_config[bmad_key]
            if isinstance(value, str):
                value = value.replace("{project-root}/", "").replace("{project-root}", "")
                paths[our_key] = value

    return paths


def load_config(project_root: Path) -> Config:
    """Load configuration from .bmadnotion.yaml.

    Args:
        project_root: Path to the project root directory.

    Returns:
        Loaded and validated configuration.

    Raises:
        ConfigNotFoundError: If .bmadnotion.yaml is not found.
    """
    config_path = project_root / ".bmadnotion.yaml"

    if not config_path.exists():
        raise ConfigNotFoundError(
            f"Configuration file not found: {config_path}\n"
            "Run 'bmadnotion init' to create one."
        )

    with open(config_path) as f:
        config_data = yaml.safe_load(f) or {}

    # Auto-discover BMAD paths if not specified
    if "paths" not in config_data:
        discovered_paths = _discover_bmad_paths(project_root)
        if discovered_paths:
            config_data["paths"] = discovered_paths

    # Create config object
    config = Config(**config_data)

    # Resolve relative paths to absolute
    config = _resolve_paths(config, project_root)

    return config
