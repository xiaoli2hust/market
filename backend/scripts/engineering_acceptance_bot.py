"""Bot center engineering acceptance checks."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _read_frontend_services() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "frontend/src/services").rglob("*.ts"))
    )


def _read_frontend_page_tree(page: str) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / f"frontend/src/pages/{page}").rglob("*.ts*"))
    )


def check_bot_enterprise_ops_contract() -> None:
    model = _read("backend/app/models.py")
    router = _read("backend/app/routers/bot.py")
    runtime = _read("backend/app/services/bot_runtime.py")
    frontend_api = _read_frontend_services()
    frontend_page = _read_frontend_page_tree("BotCenter")
    migration = _read("backend/migrations/versions/015_bot_enterprise_operations.py")
    sqlite_migration = _read("backend/app/sqlite_auto_migration.py") + _read("backend/app/sqlite_bot_migration.py")

    for class_name in (
        "BotChannelAdapter", "BotInboundEvent", "BotInboxItem", "BotHandoff",
        "BotTaskRun", "BotReleaseVersion", "BotFeedback", "BotKnowledgeSyncJob",
        "BotEnvironment", "BotCompliancePolicy",
    ):
        assert f"class {class_name}" in model, f"机器人运营模型缺少 {class_name}"
        assert class_name in runtime, f"机器人运行时缺少 {class_name}"

    for table_name in (
        "bot_channel_adapters", "bot_inbound_events", "bot_inbox_items", "bot_handoffs",
        "bot_task_runs", "bot_release_versions", "bot_feedback", "bot_knowledge_sync_jobs",
        "bot_environments", "bot_compliance_policies",
    ):
        assert table_name in migration, f"机器人运营迁移缺少 {table_name}"
        assert table_name in sqlite_migration, f"SQLite 自动迁移缺少 {table_name}"

    for route in (
        '"/channel-adapters"', '"/inbox"', '"/handoffs"', '"/task-runs"',
        '"/releases"', '"/feedback"', '"/knowledge-sync"', '"/environments"',
        '"/compliance-policies"', '"/observability-summary"',
    ):
        assert route in router, f"机器人中心缺少路由 {route}"

    for marker in (
        "fetchBotChannelAdapters", "fetchBotInbox", "createBotHandoff",
        "fetchBotReleases", "publishBotRelease", "fetchBotFeedback",
        "fetchBotKnowledgeSyncJobs", "fetchBotCompliancePolicies",
        "fetchBotObservabilitySummary",
    ):
        assert marker in frontend_api, f"前端 API 缺少 {marker}"
        assert marker in frontend_page, f"机器人中心页面未使用 {marker}"

    for label in ("生产运营", "发布观测", "合规环境", "知识同步任务", "多轮上下文"):
        assert label in frontend_page, f"机器人中心页面缺少 {label}"

    assert "implemented_bot_skill_keys" in runtime, "机器人运行时必须暴露已实现 Skill 注册表"
    assert 'BotSkill.implementation_status == "implemented"' in runtime, "机器人选 Skill 时必须跳过未实现能力"
    assert "不能作为已启用能力运行" in runtime, "未绑定执行器的 Skill 运行必须失败留痕"
    assert "implemented_bot_skill_keys" in router, "Skill 启用接口必须校验后端执行器"
    assert "不能启用" in router, "未接入执行器的 Skill 不能在管理端启用"
