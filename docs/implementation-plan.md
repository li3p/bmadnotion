# bmadnotion 实现计划

> 最后更新: 2026-01-29
> 状态: 实施中 (Phase 1)

## 项目概述

bmadnotion 是一个 BMAD 项目同步工具，用于将本地 BMAD 项目产物同步到 Notion。

### 核心功能

| 功能 | 数据源 | Notion 目标 | 描述 |
|------|--------|-------------|------|
| **Page Sync** | `planning-artifacts/*.md` | Notion Pages | PRD、架构、UX 等文档同步 |
| **Database Sync** | `sprint-status.yaml` + Story 文件 | Notion Database | Sprint 进度追踪 |

### 技术栈

- Python 3.13+
- marknotion (Markdown ↔ Notion 转换)
- SQLite (同步状态存储)
- Click (CLI)
- Pydantic (数据模型)
- pytest (测试)

### 开发方法

采用 **ATDD (验收测试驱动开发)**：
1. 先编写验收测试 (Acceptance Test)
2. 运行测试 (红灯)
3. 实现功能
4. 运行测试 (绿灯)
5. 重构

---

## Phase 1: 基础设施

**目标**: 建立项目骨架、配置系统、数据模型和存储层

### Task 1.1: 项目初始化

**状态**: `done` ✅ (2026-01-29)

**验收标准**:
- [x] AC1: `uv run pytest` 能运行（即使无测试）
- [x] AC2: `uv run bmadnotion --help` 显示帮助信息
- [x] AC3: 项目结构符合规范

**验收测试** (`tests/test_cli.py`):
```python
def test_cli_help(cli_runner):
    """AC2: CLI --help 应显示帮助信息"""
    result = cli_runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "bmadnotion" in result.output
```

**任务清单**:
- [x] 1.1.1 创建 `pyproject.toml`
- [x] 1.1.2 创建目录结构 `src/bmadnotion/`
- [x] 1.1.3 创建 `__init__.py` 和 `cli.py` 骨架
- [x] 1.1.4 配置 pytest

**产出文件**:
- `pyproject.toml`
- `src/bmadnotion/__init__.py`
- `src/bmadnotion/cli.py`
- `tests/conftest.py`
- `tests/test_cli.py`
- `README.md` (详细文档)
- `LICENSE`
- `.github/workflows/workflow.yml`

---

### Task 1.2: 配置系统

**状态**: `done` ✅ (2026-01-29)

**验收标准**:
- [x] AC1: 能加载 `.bmadnotion.yaml` 配置文件
- [x] AC2: 缺少配置文件时给出明确错误
- [x] AC3: 支持从环境变量读取 Notion Token
- [x] AC4: 支持从 `_bmad/bmm/config.yaml` 自动发现路径

**验收测试** (`tests/test_config.py`):
```python
def test_load_config_from_yaml(tmp_path):
    """AC1: 应能加载 .bmadnotion.yaml"""
    config_file = tmp_path / ".bmadnotion.yaml"
    config_file.write_text("""
project: test-project
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "abc123"
paths:
  bmad_output: "_bmad-output"
""")
    config = load_config(tmp_path)
    assert config.project == "test-project"
    assert config.notion.workspace_page_id == "abc123"

def test_config_not_found(tmp_path):
    """AC2: 缺少配置文件应抛出明确错误"""
    with pytest.raises(ConfigNotFoundError) as exc:
        load_config(tmp_path)
    assert ".bmadnotion.yaml" in str(exc.value)

def test_notion_token_from_env(tmp_path, monkeypatch):
    """AC3: 应从环境变量读取 Token"""
    monkeypatch.setenv("NOTION_TOKEN", "secret_xxx")
    # ... setup config file ...
    config = load_config(tmp_path)
    assert config.get_notion_token() == "secret_xxx"

def test_auto_discover_bmad_paths(tmp_path):
    """AC4: 应自动发现 BMAD 路径配置"""
    # 创建 _bmad/bmm/config.yaml
    bmad_config = tmp_path / "_bmad/bmm/config.yaml"
    bmad_config.parent.mkdir(parents=True)
    bmad_config.write_text("""
planning_artifacts: "{project-root}/_bmad-output/planning-artifacts"
implementation_artifacts: "{project-root}/_bmad-output/implementation-artifacts"
""")
    # 创建最小 .bmadnotion.yaml
    (tmp_path / ".bmadnotion.yaml").write_text("project: test")

    config = load_config(tmp_path)
    assert "planning-artifacts" in str(config.paths.planning_artifacts)
```

**任务清单**:
- [x] 1.2.1 定义 `Config` Pydantic 模型
- [x] 1.2.2 实现 `load_config()` 函数
- [x] 1.2.3 实现 BMAD 路径自动发现
- [x] 1.2.4 实现环境变量 Token 读取

**产出文件**:
- `src/bmadnotion/config.py`
- `tests/test_config.py` (9 个测试)

---

### Task 1.3: 数据模型

**状态**: `pending`

**验收标准**:
- [ ] AC1: Document 模型能表示 planning-artifacts 文档
- [ ] AC2: Epic/Story 模型能表示 sprint 数据
- [ ] AC3: SyncState 模型能追踪同步状态
- [ ] AC4: 模型支持序列化/反序列化

**验收测试** (`tests/test_models.py`):
```python
def test_document_model():
    """AC1: Document 模型应包含必要字段"""
    doc = Document(
        path=Path("prd.md"),
        title="PRD - bloomy",
        content="# PRD\n...",
        mtime=1234567890.0
    )
    assert doc.path == Path("prd.md")
    assert doc.title == "PRD - bloomy"

def test_epic_model():
    """AC2: Epic 模型应包含必要字段"""
    epic = Epic(
        key="epic-1",
        title="KP Graph Studio",
        status="in-progress",
        file_path=Path("epic-1-kp-graph.md"),
        mtime=1234567890.0
    )
    assert epic.key == "epic-1"
    assert epic.status == "in-progress"

def test_story_model():
    """AC2: Story 模型应包含必要字段和 epic 关联"""
    story = Story(
        key="1-5-create-knowledge-point",
        epic_key="epic-1",
        title="查看知识点详情",
        status="done",
        file_path=Path("1-5-create-knowledge-point.md"),
        mtime=1234567890.0,
        content="# Story 1.5..."
    )
    assert story.epic_key == "epic-1"
    assert story.status == "done"

def test_sync_state_serialization():
    """AC4: SyncState 应支持序列化"""
    state = PageSyncState(
        local_path="prd.md",
        notion_page_id="abc123",
        last_synced_mtime=1234567890.0,
        content_hash="md5hash"
    )
    data = state.model_dump()
    restored = PageSyncState.model_validate(data)
    assert restored == state
```

**任务清单**:
- [ ] 1.3.1 定义 Document 模型
- [ ] 1.3.2 定义 Epic/Story 模型
- [ ] 1.3.3 定义 PageSyncState/DbSyncState 模型
- [ ] 1.3.4 添加模型验证逻辑

**产出文件**:
- `src/bmadnotion/models.py`
- `tests/test_models.py`

---

### Task 1.4: SQLite 存储层

**状态**: `pending`

**验收标准**:
- [ ] AC1: 能创建/打开项目数据库文件
- [ ] AC2: 能保存和读取 PageSyncState
- [ ] AC3: 能保存和读取 DbSyncState
- [ ] AC4: 支持按 local_path/local_key 查询
- [ ] AC5: 数据库文件位于 `.bmadnotion/` 目录

**验收测试** (`tests/test_store.py`):
```python
def test_store_creates_db_file(tmp_path):
    """AC1 & AC5: 应在 .bmadnotion/ 创建数据库"""
    store = Store(project_root=tmp_path)
    assert (tmp_path / ".bmadnotion" / "sync.db").exists()

def test_save_and_get_page_state(tmp_path):
    """AC2: 应能保存和读取 PageSyncState"""
    store = Store(project_root=tmp_path)
    state = PageSyncState(
        local_path="prd.md",
        notion_page_id="abc123",
        last_synced_mtime=1234567890.0,
        content_hash="md5hash"
    )
    store.save_page_state(state)

    retrieved = store.get_page_state("prd.md")
    assert retrieved is not None
    assert retrieved.notion_page_id == "abc123"

def test_get_nonexistent_state(tmp_path):
    """AC4: 查询不存在的记录应返回 None"""
    store = Store(project_root=tmp_path)
    assert store.get_page_state("nonexistent.md") is None

def test_save_and_get_db_state(tmp_path):
    """AC3: 应能保存和读取 DbSyncState"""
    store = Store(project_root=tmp_path)
    state = DbSyncState(
        local_key="epic-1",
        entity_type="epic",
        notion_page_id="xyz789",
        last_synced_mtime=1234567890.0,
        content_hash=None
    )
    store.save_db_state(state)

    retrieved = store.get_db_state("epic-1")
    assert retrieved is not None
    assert retrieved.entity_type == "epic"
```

**任务清单**:
- [ ] 1.4.1 设计数据库 schema
- [ ] 1.4.2 实现 Store 类初始化（创建表）
- [ ] 1.4.3 实现 PageSyncState CRUD
- [ ] 1.4.4 实现 DbSyncState CRUD

**产出文件**:
- `src/bmadnotion/store.py`
- `tests/test_store.py`

---

### Task 1.5: 文件扫描器

**状态**: `pending`

**验收标准**:
- [ ] AC1: 能扫描 planning-artifacts 目录中的文档
- [ ] AC2: 能解析 sprint-status.yaml 获取 Epic/Story 列表
- [ ] AC3: 能读取 Epic 文件提取标题
- [ ] AC4: 能读取 Story 文件提取内容
- [ ] AC5: 正确处理文件不存在的情况

**验收测试** (`tests/test_scanner.py`):
```python
def test_scan_documents(tmp_path, sample_bmad_project):
    """AC1: 应扫描 planning-artifacts 文档"""
    config = load_config(tmp_path)
    scanner = BMADScanner(config)

    docs = scanner.scan_documents()

    assert len(docs) >= 1
    prd = next((d for d in docs if "prd" in d.path.name), None)
    assert prd is not None
    assert "PRD" in prd.content

def test_scan_sprint_status(tmp_path, sample_bmad_project):
    """AC2: 应解析 sprint-status.yaml"""
    config = load_config(tmp_path)
    scanner = BMADScanner(config)

    epics, stories = scanner.scan_sprint_status()

    assert len(epics) >= 1
    assert epics[0].key.startswith("epic-")
    assert len(stories) >= 1

def test_scan_epic_extracts_title(tmp_path, sample_bmad_project):
    """AC3: 应从 Epic 文件提取标题"""
    config = load_config(tmp_path)
    scanner = BMADScanner(config)

    epics, _ = scanner.scan_sprint_status()
    epic1 = next((e for e in epics if e.key == "epic-1"), None)

    assert epic1 is not None
    assert epic1.title != ""  # 标题已提取

def test_scan_story_extracts_content(tmp_path, sample_bmad_project):
    """AC4: 应从 Story 文件提取内容"""
    config = load_config(tmp_path)
    scanner = BMADScanner(config)

    _, stories = scanner.scan_sprint_status()
    # 找一个 ready-for-dev 或更高状态的 story (有文件)
    story_with_file = next(
        (s for s in stories if s.status != "backlog"),
        None
    )

    if story_with_file:
        assert story_with_file.content is not None
        assert "## Story" in story_with_file.content

def test_scan_handles_missing_files(tmp_path):
    """AC5: 应优雅处理文件不存在"""
    # 创建只有 sprint-status.yaml 但没有 story 文件的项目
    config = create_minimal_config(tmp_path)
    scanner = BMADScanner(config)

    epics, stories = scanner.scan_sprint_status()

    # backlog 状态的 story 没有文件，应该 content=None
    backlog_story = next((s for s in stories if s.status == "backlog"), None)
    if backlog_story:
        assert backlog_story.file_path is None
        assert backlog_story.content is None
```

**任务清单**:
- [ ] 1.5.1 实现 `scan_documents()` 方法
- [ ] 1.5.2 实现 `scan_sprint_status()` 方法
- [ ] 1.5.3 实现 Epic 文件解析（提取标题）
- [ ] 1.5.4 实现 Story 文件解析（提取内容）
- [ ] 1.5.5 创建测试 fixtures (sample_bmad_project)

**产出文件**:
- `src/bmadnotion/scanner.py`
- `tests/test_scanner.py`
- `tests/fixtures/` (示例 BMAD 项目结构)

---

## Phase 2: Page Sync (Planning Artifacts)

**目标**: 实现 planning-artifacts → Notion Pages 同步

### Task 2.1: Page 同步引擎核心

**状态**: `pending`

**验收标准**:
- [ ] AC1: 能将 Markdown 文档创建为 Notion Page
- [ ] AC2: 能更新已存在的 Notion Page
- [ ] AC3: 使用 content hash 判断是否需要同步
- [ ] AC4: 同步后更新 Store 中的状态

**验收测试** (`tests/test_page_sync.py`):
```python
@pytest.mark.integration
def test_create_new_page(notion_client, tmp_path, sample_bmad_project):
    """AC1: 应能创建新 Notion Page"""
    config = load_config(tmp_path)
    store = Store(tmp_path)
    engine = PageSyncEngine(notion_client, store, config)

    result = engine.sync()

    assert result.created > 0
    # 验证 Notion 上确实创建了页面
    state = store.get_page_state("prd.md")
    assert state is not None
    assert state.notion_page_id is not None

@pytest.mark.integration
def test_update_existing_page(notion_client, tmp_path, sample_bmad_project):
    """AC2: 应能更新已存在的 Page"""
    config = load_config(tmp_path)
    store = Store(tmp_path)
    engine = PageSyncEngine(notion_client, store, config)

    # 第一次同步
    engine.sync()

    # 修改本地文件
    prd_path = tmp_path / "_bmad-output/planning-artifacts/prd.md"
    prd_path.write_text(prd_path.read_text() + "\n## New Section")

    # 第二次同步
    result = engine.sync()

    assert result.updated > 0

def test_skip_unchanged_document(tmp_path, sample_bmad_project, mock_notion_client):
    """AC3: 未变更的文档应跳过"""
    config = load_config(tmp_path)
    store = Store(tmp_path)
    engine = PageSyncEngine(mock_notion_client, store, config)

    # 第一次同步
    engine.sync()

    # 重置 mock 调用计数
    mock_notion_client.reset_mock()

    # 第二次同步（无变更）
    result = engine.sync()

    assert result.skipped > 0
    assert mock_notion_client.create_page.call_count == 0
    assert mock_notion_client.update_page.call_count == 0

def test_sync_updates_store(tmp_path, sample_bmad_project, mock_notion_client):
    """AC4: 同步后应更新 Store"""
    config = load_config(tmp_path)
    store = Store(tmp_path)
    engine = PageSyncEngine(mock_notion_client, store, config)

    engine.sync()

    state = store.get_page_state("prd.md")
    assert state is not None
    assert state.last_synced_mtime > 0
    assert state.content_hash is not None
```

**任务清单**:
- [ ] 2.1.1 实现 PageSyncEngine 类
- [ ] 2.1.2 实现 `_needs_sync()` 判断逻辑
- [ ] 2.1.3 实现创建新 Page 逻辑
- [ ] 2.1.4 实现更新现有 Page 逻辑
- [ ] 2.1.5 集成 marknotion 转换

**产出文件**:
- `src/bmadnotion/page_sync.py`
- `tests/test_page_sync.py`

---

### Task 2.2: Page Sync CLI

**状态**: `pending`

**验收标准**:
- [ ] AC1: `bmadnotion sync pages` 执行 Page 同步
- [ ] AC2: `--force` 参数强制全量同步
- [ ] AC3: `--dry-run` 参数预览变更
- [ ] AC4: 同步结果显示统计信息

**验收测试** (`tests/test_cli_page_sync.py`):
```python
def test_sync_pages_command(cli_runner, tmp_path, sample_bmad_project, mock_notion):
    """AC1: sync pages 应执行同步"""
    result = cli_runner.invoke(cli, ["sync", "pages"],
                               env={"NOTION_TOKEN": "test"})
    assert result.exit_code == 0
    assert "Synced" in result.output

def test_sync_pages_force(cli_runner, tmp_path, sample_bmad_project, mock_notion):
    """AC2: --force 应强制全量同步"""
    # 先同步一次
    cli_runner.invoke(cli, ["sync", "pages"])

    # 用 --force 再次同步
    result = cli_runner.invoke(cli, ["sync", "pages", "--force"])

    assert result.exit_code == 0
    # force 模式下即使无变更也会同步

def test_sync_pages_dry_run(cli_runner, tmp_path, sample_bmad_project):
    """AC3: --dry-run 应预览但不执行"""
    result = cli_runner.invoke(cli, ["sync", "pages", "--dry-run"])

    assert result.exit_code == 0
    assert "Would sync" in result.output or "Dry run" in result.output
    # 验证没有实际调用 Notion API

def test_sync_pages_shows_stats(cli_runner, tmp_path, sample_bmad_project, mock_notion):
    """AC4: 应显示同步统计"""
    result = cli_runner.invoke(cli, ["sync", "pages"])

    assert "Created:" in result.output or "Updated:" in result.output
```

**任务清单**:
- [ ] 2.2.1 添加 `sync pages` 子命令
- [ ] 2.2.2 实现 `--force` 参数
- [ ] 2.2.3 实现 `--dry-run` 参数
- [ ] 2.2.4 实现统计信息输出

**产出文件**:
- `src/bmadnotion/cli.py` (更新)
- `tests/test_cli_page_sync.py`

---

## Phase 3: Database Sync (Sprint Tracking)

**目标**: 实现 sprint-status → Notion Database 同步

### Task 3.1: Database 同步引擎核心

**状态**: `pending`

**验收标准**:
- [ ] AC1: 能将 Epic 同步到 Sprints Database
- [ ] AC2: 能将 Story 同步到 Tasks Database
- [ ] AC3: Story 能关联到对应的 Sprint (Relation)
- [ ] AC4: Story 内容转换为 Page blocks
- [ ] AC5: 状态值正确映射 (local → Notion)

**验收测试** (`tests/test_db_sync.py`):
```python
@pytest.mark.integration
def test_sync_epic_to_sprints_db(notion_client, tmp_path, sample_bmad_project):
    """AC1: 应将 Epic 同步到 Sprints Database"""
    config = load_config(tmp_path)
    store = Store(tmp_path)
    engine = DbSyncEngine(notion_client, store, config)

    result = engine.sync()

    assert result.epics_synced > 0
    # 验证 Database 中有记录
    state = store.get_db_state("epic-1")
    assert state is not None

@pytest.mark.integration
def test_sync_story_to_tasks_db(notion_client, tmp_path, sample_bmad_project):
    """AC2: 应将 Story 同步到 Tasks Database"""
    config = load_config(tmp_path)
    store = Store(tmp_path)
    engine = DbSyncEngine(notion_client, store, config)

    result = engine.sync()

    assert result.stories_synced > 0

@pytest.mark.integration
def test_story_relates_to_sprint(notion_client, tmp_path, sample_bmad_project):
    """AC3: Story 应关联到对应 Sprint"""
    config = load_config(tmp_path)
    store = Store(tmp_path)
    engine = DbSyncEngine(notion_client, store, config)

    engine.sync()

    # 查询 Notion 验证 Relation
    story_state = store.get_db_state("1-1-backend-setup")
    epic_state = store.get_db_state("epic-1")

    # 获取 story page 并验证 relation
    story_page = notion_client.get_page(story_state.notion_page_id)
    sprint_relation = story_page["properties"]["Sprint"]["relation"]
    assert any(r["id"] == epic_state.notion_page_id for r in sprint_relation)

def test_story_content_as_blocks(tmp_path, sample_bmad_project, mock_notion_client):
    """AC4: Story 内容应转换为 Notion blocks"""
    config = load_config(tmp_path)
    store = Store(tmp_path)
    engine = DbSyncEngine(mock_notion_client, store, config)

    engine.sync()

    # 验证 append_blocks 被调用，且包含正确内容
    calls = mock_notion_client.append_blocks.call_args_list
    assert len(calls) > 0
    # 检查 blocks 结构

def test_status_mapping(tmp_path, sample_bmad_project, mock_notion_client):
    """AC5: 状态应正确映射"""
    config = load_config(tmp_path)
    store = Store(tmp_path)
    engine = DbSyncEngine(mock_notion_client, store, config)

    engine.sync()

    # 验证 "in-progress" 映射为 "In Progress"
    create_calls = mock_notion_client.create_database_entry.call_args_list
    # 检查 properties 中的 Status 值
```

**任务清单**:
- [ ] 3.1.1 实现 DbSyncEngine 类
- [ ] 3.1.2 实现 Epic 同步逻辑
- [ ] 3.1.3 实现 Story 同步逻辑
- [ ] 3.1.4 实现 Relation 建立
- [ ] 3.1.5 实现状态映射

**产出文件**:
- `src/bmadnotion/db_sync.py`
- `tests/test_db_sync.py`

---

### Task 3.2: Database Sync CLI

**状态**: `pending`

**验收标准**:
- [ ] AC1: `bmadnotion sync db` 执行 Database 同步
- [ ] AC2: 支持 `--force` 和 `--dry-run`
- [ ] AC3: 显示 Epic/Story 同步统计

**验收测试** (`tests/test_cli_db_sync.py`):
```python
def test_sync_db_command(cli_runner, tmp_path, sample_bmad_project, mock_notion):
    """AC1: sync db 应执行同步"""
    result = cli_runner.invoke(cli, ["sync", "db"])
    assert result.exit_code == 0
    assert "Epic" in result.output or "Story" in result.output

def test_sync_db_shows_stats(cli_runner, tmp_path, sample_bmad_project, mock_notion):
    """AC3: 应显示同步统计"""
    result = cli_runner.invoke(cli, ["sync", "db"])

    assert "Epics:" in result.output
    assert "Stories:" in result.output
```

**任务清单**:
- [ ] 3.2.1 添加 `sync db` 子命令
- [ ] 3.2.2 实现参数和统计输出

**产出文件**:
- `src/bmadnotion/cli.py` (更新)
- `tests/test_cli_db_sync.py`

---

### Task 3.3: 组合同步命令

**状态**: `pending`

**验收标准**:
- [ ] AC1: `bmadnotion sync` (无参数) 同步所有
- [ ] AC2: `bmadnotion sync --pages-only` 仅同步 Pages
- [ ] AC3: `bmadnotion sync --db-only` 仅同步 Database
- [ ] AC4: 错误时给出明确提示，不中断其他同步

**任务清单**:
- [ ] 3.3.1 实现组合同步逻辑
- [ ] 3.3.2 实现错误隔离

**产出文件**:
- `src/bmadnotion/cli.py` (更新)
- `tests/test_cli_sync.py`

---

## Phase 4: 完善与发布

**目标**: 错误处理、文档、发布

### Task 4.1: 初始化与状态命令

**状态**: `pending`

**验收标准**:
- [ ] AC1: `bmadnotion init` 创建配置文件
- [ ] AC2: `bmadnotion status` 显示同步状态
- [ ] AC3: 状态显示本地 vs Notion 差异

**任务清单**:
- [ ] 4.1.1 实现 `init` 命令
- [ ] 4.1.2 实现 `status` 命令
- [ ] 4.1.3 实现差异检测

---

### Task 4.2: 错误处理与重试

**状态**: `pending`

**验收标准**:
- [ ] AC1: Notion API 错误有明确提示
- [ ] AC2: 支持自动重试 (rate limit)
- [ ] AC3: 部分失败不影响其他项同步

**任务清单**:
- [ ] 4.2.1 添加错误类型定义
- [ ] 4.2.2 集成 marknotion 的重试机制
- [ ] 4.2.3 实现错误隔离

---

### Task 4.3: 文档与发布

**状态**: `pending`

**验收标准**:
- [ ] AC1: README 包含安装和使用说明
- [ ] AC2: 配置文件格式有完整文档
- [ ] AC3: PyPI 发布成功

**任务清单**:
- [ ] 4.3.1 编写 README.md
- [ ] 4.3.2 编写配置文档
- [ ] 4.3.3 设置 GitHub Actions 发布

---

## 进度追踪

| Phase | Task | 状态 | 完成日期 |
|-------|------|------|----------|
| 1 | 1.1 项目初始化 | `done` ✅ | 2026-01-29 |
| 1 | 1.2 配置系统 | `done` ✅ | 2026-01-29 |
| 1 | 1.3 数据模型 | `pending` | - |
| 1 | 1.4 SQLite 存储层 | `pending` | - |
| 1 | 1.5 文件扫描器 | `pending` | - |
| 2 | 2.1 Page 同步引擎 | `pending` | - |
| 2 | 2.2 Page Sync CLI | `pending` | - |
| 3 | 3.1 Database 同步引擎 | `pending` | - |
| 3 | 3.2 Database Sync CLI | `pending` | - |
| 3 | 3.3 组合同步命令 | `pending` | - |
| 4 | 4.1 初始化与状态命令 | `pending` | - |
| 4 | 4.2 错误处理与重试 | `pending` | - |
| 4 | 4.3 文档与发布 | `pending` | - |

---

## 测试策略

### 测试分层

```
tests/
├── unit/                    # 单元测试 (无外部依赖)
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_store.py
│   └── test_scanner.py
│
├── integration/             # 集成测试 (使用 mock Notion)
│   ├── test_page_sync.py
│   └── test_db_sync.py
│
├── e2e/                     # 端到端测试 (真实 Notion API)
│   └── test_full_sync.py   # 需要 NOTION_TOKEN
│
├── fixtures/                # 测试数据
│   └── sample_bmad_project/
│
└── conftest.py             # 共享 fixtures
```

### 运行测试

```bash
# 所有单元测试
uv run pytest tests/unit/

# 集成测试 (使用 mock)
uv run pytest tests/integration/

# E2E 测试 (需要真实 Token)
NOTION_TOKEN=xxx uv run pytest tests/e2e/ -m integration

# 全部测试
uv run pytest

# 覆盖率报告
uv run pytest --cov=bmadnotion --cov-report=html
```

---

## 依赖关系

```
marknotion (已完成)
    │
    ├── markdown_to_blocks()
    ├── blocks_to_markdown()
    └── NotionClient
            │
            ▼
    bmadnotion (本项目)
        │
        ├── config.py ─────────────────┐
        ├── models.py ─────────────────┤
        ├── store.py ──────────────────┤
        ├── scanner.py ────────────────┤
        │                              │
        ├── page_sync.py ◄─────────────┤
        ├── db_sync.py ◄───────────────┤
        │                              │
        └── cli.py ◄───────────────────┘
```
