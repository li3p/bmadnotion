# bmadnotion

[![PyPI version](https://badge.fury.io/py/bmadnotion.svg)](https://badge.fury.io/py/bmadnotion)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Sync [BMAD](https://docs.bmad-method.org/) project artifacts to Notion. Keep your planning documents and sprint tracking in sync between local files and Notion workspace.

## Features

- **Page Sync**: Sync planning artifacts (PRD, Architecture, UX Design) to Notion Pages
- **Database Sync**: Sync sprint status (Epics, Stories) to Notion Databases
- **Incremental Sync**: Only sync changed files based on content hash
- **BMAD Native**: Understands BMAD project structure and conventions

## Installation

```bash
pip install bmadnotion
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add bmadnotion
```

## Quick Start

### 1. Initialize Configuration

```bash
cd your-bmad-project
bmadnotion init
```

This creates `.bmadnotion.yaml` configuration file.

### 2. Configure Notion

Set your Notion integration token:

```bash
export NOTION_TOKEN=your_notion_integration_token
```

Edit `.bmadnotion.yaml` to set your Notion workspace page ID:

```yaml
project: my-project
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "your-workspace-page-id"
```

### 3. Sync

```bash
# Sync everything
bmadnotion sync

# Sync only planning documents (Pages)
bmadnotion sync pages

# Sync only sprint tracking (Database)
bmadnotion sync db

# Preview changes without syncing
bmadnotion sync --dry-run

# Force full sync (ignore cache)
bmadnotion sync --force
```

### 4. Check Status

```bash
bmadnotion status
```

## Configuration

### `.bmadnotion.yaml` Reference

```yaml
# Project name
project: bloomy

# Notion configuration
notion:
  token_env: NOTION_TOKEN           # Environment variable name for token
  workspace_page_id: "abc123..."    # Root page for synced content

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
  parent_page_id: "..."             # Parent page for documents
  documents:
    - path: "prd.md"
      title: "PRD - {project}"
    - path: "architecture.md"
      title: "Architecture - {project}"
    - path: "ux-design-specification.md"
      title: "UX Design - {project}"
    - path: "product-brief.md"
      title: "Product Brief - {project}"

# Database sync configuration
database_sync:
  enabled: true

  sprints:
    database_id: "..."              # Notion database ID for Sprints
    status_mapping:
      backlog: "Not Started"
      in-progress: "In Progress"
      done: "Done"

  tasks:
    database_id: "..."              # Notion database ID for Tasks
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
│   ├── planning-artifacts/       # → Notion Pages
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
└── .bmadnotion.yaml              # bmadnotion config
```

## Sync Behavior

### Page Sync (Planning Artifacts)

| Local File | Notion |
|------------|--------|
| `prd.md` | Page: "PRD - {project}" |
| `architecture.md` | Page: "Architecture - {project}" |
| `ux-design-specification.md` | Page: "UX Design - {project}" |

- Creates new pages if not exist
- Updates existing pages if content changed (based on MD5 hash)
- Preserves Notion page IDs across syncs

### Database Sync (Sprint Tracking)

| Local | Notion |
|-------|--------|
| `epic-N` in sprint-status.yaml | Row in Sprints database |
| `N-M-story-name` in sprint-status.yaml | Row in Tasks database |
| Story file content | Page content in Task row |

- Syncs Epic/Story status
- Creates Relation between Task and Sprint
- Story file content becomes page blocks

## CLI Reference

```bash
# Initialize project
bmadnotion init [--project NAME]

# Sync all
bmadnotion sync [--force] [--dry-run]

# Sync pages only
bmadnotion sync pages [--force] [--dry-run]

# Sync database only
bmadnotion sync db [--force] [--dry-run]

# Show sync status
bmadnotion status

# Show configuration
bmadnotion config show
```

## Notion Setup

### 1. Create a Notion Integration

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Click "New integration"
3. Give it a name (e.g., "bmadnotion")
4. Select the workspace
5. Copy the "Internal Integration Token"

### 2. Share Pages/Databases with Integration

1. Open the parent page where documents will be synced
2. Click "..." menu → "Add connections"
3. Select your integration
4. Repeat for any databases you want to sync to

### 3. Get Page/Database IDs

Page and database IDs are in the URL:
- `https://notion.so/Your-Page-**abc123def456**` → ID is `abc123def456`
- `https://notion.so/**abc123def456**?v=...` → ID is `abc123def456`

## Troubleshooting

### "Token not found" error
```bash
# Make sure NOTION_TOKEN is set
export NOTION_TOKEN=your_token_here

# Verify it's set
echo $NOTION_TOKEN
```

### "Page not found" error
- Ensure the integration has access to the page
- Check that the page ID is correct

### "Database not found" error
- Ensure the integration has access to the database
- Verify database ID in configuration

### Sync not detecting changes
- bmadnotion uses content hash to detect changes
- Use `--force` to sync everything regardless of cache

## Requirements

- Python 3.13+
- Notion Integration Token with appropriate permissions:
  - Read/Write access to pages
  - Read/Write access to databases

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
