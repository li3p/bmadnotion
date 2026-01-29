# bmadnotion

[![PyPI version](https://badge.fury.io/py/bmadnotion.svg)](https://badge.fury.io/py/bmadnotion)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Sync [BMAD](https://docs.bmad-method.org/) project artifacts to Notion. Keep your planning documents and sprint tracking in sync between local files and Notion workspace.

## Features

- **Projects Integration**: Automatically create Project rows in the Projects database
- **Page Sync**: Sync planning artifacts (PRD, Architecture, UX Design) as sub-pages under Project
- **Database Sync**: Sync sprint status (Epics → Sprints, Stories → Tasks)
- **Relation Linking**: Stories link to both their Sprint (Epic) and Project
- **Incremental Sync**: Only sync changed files based on content hash
- **BMAD Native**: Understands BMAD project structure and conventions

## Installation

### As a CLI tool (recommended)

```bash
# With uv (recommended)
uv tool install bmadnotion

# Or with pipx
pipx install bmadnotion
```

### As a project dependency

```bash
# With uv
uv add bmadnotion

# Or with pip
pip install bmadnotion
```

## Quick Start

### 1. Initialize Configuration

```bash
cd your-bmad-project
bmad init
```

This creates `.bmadnotion.yaml` configuration file.

### 2. Configure Notion

Set your Notion integration token (choose one):

```bash
# Option A: Use .env file (recommended)
echo "NOTION_TOKEN=your_notion_integration_token" >> .env

# Option B: Export in shell
export NOTION_TOKEN=your_notion_integration_token
```

Edit `.bmadnotion.yaml` to set your database IDs:

```yaml
project: my-project
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "your-workspace-page-id"

database_sync:
  enabled: true
  projects:
    database_id: "your-projects-database-id"
  sprints:
    database_id: "your-sprints-database-id"
  tasks:
    database_id: "your-tasks-database-id"
```

### 3. Set Up Database Fields

```bash
bmad setup-db
```

This adds required sync key fields (BMADProject, BMADEpic, BMADStory) to your databases.

### 4. Sync

```bash
# Sync everything
bmad sync

# Sync only planning documents (Pages)
bmad sync pages

# Sync only sprint tracking (Database)
bmad sync db

# Preview changes without syncing
bmad sync --dry-run

# Force full sync (ignore cache)
bmad sync --force
```

### 5. Check Status

```bash
bmad status
```

## How It Works

### Sync Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      Notion Workspace                        │
├─────────────────────────────────────────────────────────────┤
│  Projects Database                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Project: "my-project" (BMADProject: "my-project")   │   │
│  │   └── Sub-pages:                                     │   │
│  │         ├── PRD - my-project                         │   │
│  │         ├── Architecture - my-project                │   │
│  │         └── UX Design - my-project                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  Sprints Database                                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Epic 1: "User Management" (BMADEpic: "epic-1")      │   │
│  │ Epic 2: "Payment System" (BMADEpic: "epic-2")       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  Tasks Database                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Story: "Create login page" (BMADStory: "1-1-login") │   │
│  │   ├── Sprint: Epic 1 (Relation)                     │   │
│  │   ├── Project: my-project (Relation)                │   │
│  │   └── Content: [Story markdown as blocks]           │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### What Gets Synced

| Local | Notion | Details |
|-------|--------|---------|
| Project name | Projects database row | Auto-created, serves as parent for documents |
| `prd.md` | Sub-page under Project | Planning artifact |
| `architecture.md` | Sub-page under Project | Planning artifact |
| `epic-N` in sprint-status.yaml | Sprints database row | With BMADEpic key |
| `N-M-story` in sprint-status.yaml | Tasks database row | With BMADStory key, relations to Sprint & Project |

## Configuration

### `.bmadnotion.yaml` Reference

```yaml
# Project name (used as Project row title)
project: bloomy

# Notion configuration
notion:
  token_env: NOTION_TOKEN           # Environment variable name for token
  workspace_page_id: "abc123..."    # Root page for reference

# BMAD paths (auto-detected from _bmad/bmm/config.yaml if not specified)
paths:
  bmad_output: "_bmad-output"
  planning_artifacts: "_bmad-output/planning-artifacts"
  implementation_artifacts: "_bmad-output/implementation-artifacts"
  epics_dir: "_bmad-output/planning-artifacts/epics"
  sprint_status: "_bmad-output/implementation-artifacts/sprint-status.yaml"

# Page sync configuration
page_sync:
  enabled: true
  # Fallback parent page (used if Projects database not configured)
  parent_page_id: "..."
  documents:
    - path: "prd.md"
      title: "PRD - {project}"
    - path: "architecture.md"
      title: "Architecture - {project}"
    - path: "ux-design-specification.md"
      title: "UX Design - {project}"

# Database sync configuration
database_sync:
  enabled: true

  # Projects database (for Project row and document sub-pages)
  projects:
    database_id: "..."              # Notion database ID for Projects
    key_property: "BMADProject"     # Field to store BMAD project key
    name_property: "Project name"   # Title field name

  # Sprints database (for Epics)
  sprints:
    database_id: "..."              # Notion database ID for Sprints
    key_property: "BMADEpic"        # Field to store BMAD epic key
    status_mapping:
      backlog: "Not Started"
      in-progress: "In Progress"
      done: "Done"

  # Tasks database (for Stories)
  tasks:
    database_id: "..."              # Notion database ID for Tasks
    key_property: "BMADStory"       # Field to store BMAD story key
    status_mapping:
      backlog: "Backlog"
      ready-for-dev: "Ready"
      in-progress: "In Progress"
      review: "Review"
      done: "Done"
```

## BMAD Project Structure

bmadnotion expects a standard BMAD project structure:

```
your-project/
├── _bmad/
│   └── bmm/
│       └── config.yaml           # BMAD configuration
├── _bmad-output/
│   ├── planning-artifacts/       # → Notion Pages (sub-pages of Project)
│   │   ├── prd.md
│   │   ├── architecture.md
│   │   ├── ux-design-specification.md
│   │   └── epics/
│   │       ├── epic-1-*.md
│   │       └── epic-2-*.md
│   └── implementation-artifacts/ # → Notion Database
│       ├── sprint-status.yaml    # Sprint tracking
│       ├── 1-1-story-name.md     # Story files
│       └── 1-2-another-story.md
├── .bmadnotion.yaml              # bmadnotion config
└── .env                          # NOTION_TOKEN (optional)
```

## CLI Reference

```bash
# Initialize project
bmad init [--project NAME] [--force]

# Set up database fields (adds BMADProject, BMADEpic, BMADStory)
bmad setup-db

# Sync all
bmad sync [--force] [--dry-run]

# Sync pages only (planning artifacts)
bmad sync pages [--force] [--dry-run]

# Sync database only (epics and stories)
bmad sync db [--force] [--dry-run]

# Show sync status
bmad status

# Show configuration
bmad config show
```

> Note: `bmadnotion` command also works (alias for `bmad`).

## Notion Setup

### 0. Set Up Notion Workspace (Recommended)

For the best experience with bmadnotion's database sync, we recommend using the official Agile Project Management template:

1. Go to [Agile Project Management Template](https://www.notion.com/templates/agile-project-management-notion)
2. Click "Get template" to add it to your workspace
3. This template includes:
   - **Projects** database (for BMAD projects and their documents)
   - **Sprints** database (for Epics)
   - **Tasks** database (for Stories)
   - Pre-configured views and relations

You can also create your own databases, but ensure they have the required properties (Status, Title, Relations).

### 1. Create a Notion Integration

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Click "New integration"
3. Give it a name (e.g., "bmadnotion")
4. Select the workspace
5. Copy the "Internal Integration Token"

### 2. Share Databases with Integration

For each database (Projects, Sprints, Tasks):
1. Open the database
2. Click "..." menu → "Add connections"
3. Select your integration

### 3. Get Database IDs

Database IDs are in the URL:
- `https://notion.so/**abc123def456**?v=...` → ID is `abc123def456`

### 4. Run Setup

```bash
bmad setup-db
```

This adds the required sync key fields if they don't exist.

## Troubleshooting

### "Token not found" error
```bash
# Option A: Create .env file in project root
echo "NOTION_TOKEN=your_token_here" > .env

# Option B: Export in shell
export NOTION_TOKEN=your_token_here

# Verify it's set
echo $NOTION_TOKEN
```

### "Page not found" / "Database not found" error
- Ensure the integration has access to the database
- Go to the database → "..." → "Add connections" → Select your integration
- Verify database ID in configuration

### Sync not detecting changes
- bmadnotion uses content hash to detect changes
- Use `--force` to sync everything regardless of cache

### "Property not found" error
- Run `bmad setup-db` to add required fields to databases

## Requirements

- Python 3.13+
- Notion Integration Token with appropriate permissions:
  - Read/Write access to databases (Projects, Sprints, Tasks)

## Related Projects

- [marknotion](https://github.com/li3p/marknotion) - Markdown ↔ Notion blocks conversion
- [BMAD Method](https://docs.bmad-method.org/) - Breakthrough Method of Agile AI-Driven Development

## Development

```bash
# Clone the repository
git clone git@github.com:li3p/bmadnotion.git
cd bmadnotion

# Install dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=bmadnotion --cov-report=html
```

## License

MIT License - see [LICENSE](LICENSE) for details.
