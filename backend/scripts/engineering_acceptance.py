"""Engineering acceptance checks for Market product."""

from __future__ import annotations

import ast
import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

from engineering_acceptance_deploy import (
    check_container_deploy_contract,
    check_public_deployment_toolkit_contract,
    check_public_html_response_contract,
)
from engineering_acceptance_crawler import check_crawler_runtime_guard_contract

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


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


def check_long_task_timeout_contract() -> None:
    api = _read_frontend_services()
    assert "const LONG_TASK_TIMEOUT_MS = 300000" in api, "前端必须为长任务定义统一超时"
    assert "const CRAWLER_TASK_TIMEOUT_MS = 1800000" in api, "前端必须为公开网站采集定义爬虫专用超时"
    for function_name in (
        "generateReport",
        "pushReport",
        "generateExpress",
        "pushExpress",
        "generateBiddingExpress",
        "pushBiddingExpress",
        "discoverOpportunityLeads",
    ):
        marker = f"export async function {function_name}"
        assert marker in api, f"缺少长任务函数 {function_name}"
        start = api.index(marker)
        end = api.find("\nexport ", start + 1)
        block = api[start:] if end == -1 else api[start:end]
        assert "timeout: LONG_TASK_TIMEOUT_MS" in block, f"{function_name} 必须使用长任务超时"
    for function_name in ("triggerCrawler", "triggerAllCrawlers"):
        marker = f"export async function {function_name}"
        assert marker in api, f"缺少采集函数 {function_name}"
        start = api.index(marker)
        end = api.find("\nexport ", start + 1)
        block = api[start:] if end == -1 else api[start:end]
        assert "timeout: CRAWLER_TASK_TIMEOUT_MS" in block, f"{function_name} 必须使用爬虫专用超时"


def check_default_upload_key_is_not_active() -> None:
    from app.auth import _active_legacy_upload_key

    assert _active_legacy_upload_key("") is None
    assert _active_legacy_upload_key("change-me-in-production") is None
    assert _active_legacy_upload_key("please-change-me") is None
    assert _active_legacy_upload_key("real-local-key") == "real-local-key"


def check_secret_store_contract() -> None:
    from app.secret_store import decrypt_secret, encrypt_secret, _derive_key, _legacy_xor_stream

    plain = "secret-contract-check"
    encrypted = encrypt_secret(plain)
    assert encrypted and encrypted.startswith("enc:v2:"), "新写入运行时密钥必须使用 enc:v2"
    assert decrypt_secret(encrypted) == plain, "enc:v2 密钥必须可解密"

    salt = b"1" * 16
    nonce = b"2" * 16
    key = _derive_key(salt)
    ciphertext = _legacy_xor_stream(plain.encode("utf-8"), key, nonce)
    tag = hmac.new(key, b"secret-store-v1" + nonce + ciphertext, hashlib.sha256).digest()[:16]
    legacy = "enc:v1:" + base64.urlsafe_b64encode(salt + nonce + tag + ciphertext).decode("ascii").rstrip("=")
    assert decrypt_secret(legacy) == plain, "旧 enc:v1 密钥必须保持兼容读取"


def check_webhook_url_is_encrypted() -> None:
    settings_router = _read("backend/app/routers/settings.py")
    dingtalk_service = _read("backend/app/services/dingtalk_service.py")
    sqlite_migration = (
        _read("backend/app/sqlite_auto_migration.py")
        + _read("backend/app/sqlite_bot_migration.py")
    )
    assert "webhook_url = decrypt_secret(row.webhook_url)" in settings_router, "管理页读取 Webhook 必须解密"
    assert "row.webhook_url = encrypt_secret(webhook)" in settings_router, "保存 Webhook 必须加密"
    assert "decrypt_secret(row.webhook_url)" in dingtalk_service, "发送服务读取 Webhook 必须解密"
    assert '"webhook_url", "secret", "app_secret"' in sqlite_migration, "SQLite 历史 Webhook 明文必须自动加密"


def check_dingtalk_identity_contract() -> None:
    model = _read("backend/app/models.py")
    settings_router = _read("backend/app/routers/settings.py")
    frontend = _read_frontend_page_tree("Management")
    api = _read_frontend_services()
    migration = _read("backend/migrations/versions/010_dingtalk_app_identity_fields.py")
    for marker in ('app_id', 'agent_id'):
        assert marker in model, f"钉钉配置模型缺少 {marker}"
        assert marker in settings_router, f"钉钉配置接口缺少 {marker}"
        assert marker in api, f"前端 API 类型缺少 {marker}"
        assert marker in migration, f"数据库迁移缺少 {marker}"
    assert "Client ID（原 AppKey）" in frontend, "前端必须使用钉钉当前字段口径"
    assert "原企业内部应用 AgentId" in frontend, "前端必须保留旧 AgentId 记录字段"
    assert "不是旧 AgentId" in frontend, "前端必须提醒 AgentId 不等同于 RobotCode"


def check_aipaas_sync_contract() -> None:
    model = _read("backend/app/models.py")
    service = _read("backend/app/services/aipaas_service.py")
    router = _read("backend/app/routers/aipaas_sync.py")
    scheduler = _read("backend/app/services/crawler_scheduler.py")
    frontend = _read_frontend_page_tree("Management")
    api = _read_frontend_services()
    migration = _read("backend/migrations/versions/016_aipaas_config_and_crawler_item_flags.py")

    assert "AipaasConfig" in model, "AIPAAS 配置模型缺少 AipaasConfig"
    for marker in ("sync_users", "last_sync_result"):
        assert marker in model, f"AIPAAS 配置模型缺少 {marker}"
        assert marker in migration, f"AIPAAS 迁移缺少 {marker}"
    assert "aipaas_configs" in migration, "AIPAAS 迁移必须创建配置表"
    assert "get_runtime_aipaas_config(db)" in service, "AIPAAS 服务必须优先读取管理中心配置"
    assert "upsert_runtime_aipaas_config" in router, "AIPAAS 配置必须持久化保存"
    assert "normalize_aipaas_users" in service, "AIPAAS 人员清单必须清洗去重"
    assert "pull_aipaas_daily_reports(db)" in scheduler, "AIPAAS 调度器必须真实执行同步"
    assert "日报同步源" in frontend and "triggerAipaasSync" in frontend, "管理中心必须提供 AIPAAS 配置和手动同步入口"
    assert "timeout: LONG_TASK_TIMEOUT_MS" in api, "AIPAAS 手动同步必须使用长任务超时"


def check_browser_session_cookie_contract() -> None:
    auth_router = _read("backend/app/routers/auth.py")
    auth_dep = _read("backend/app/auth.py")
    api = _read_frontend_services()
    app = _read("frontend/src/app.tsx")
    compose = _read("docker-compose.yml")

    assert "response.set_cookie" in auth_router, "登录成功必须写入浏览器会话 Cookie"
    assert "httponly=True" in auth_router, "浏览器会话 Cookie 必须启用 HttpOnly"
    assert "secure=settings.AUTH_COOKIE_SECURE" in auth_router, "Cookie secure 策略必须由配置控制"
    assert "samesite=settings.AUTH_COOKIE_SAMESITE" in auth_router, "Cookie SameSite 策略必须由配置控制"
    assert "response.delete_cookie" in auth_router, "退出登录必须清理服务端会话 Cookie"
    assert "session_token" in auth_dep and "Cookie(default=None" in auth_dep, "鉴权依赖必须支持从 Cookie 读取会话"
    assert "market_token" not in api, "前端不得在 localStorage 保存 JWT token"
    assert "Authorization: `Bearer" not in app, "浏览器请求不得继续拼接可读 Bearer token"
    assert "credentials: 'same-origin'" in api and "credentials: 'same-origin'" in app, "前端请求必须携带同源 Cookie"
    assert "AUTH_COOKIE_SECURE" in compose and "AUTH_COOKIE_SAMESITE" in compose, "容器部署必须暴露 Cookie 安全配置"


def check_login_rate_limit_contract() -> None:
    auth_router = _read("backend/app/routers/auth.py")
    assert "_LOGIN_FAILURE_WINDOW = timedelta(minutes=15)" in auth_router, "登录失败限流必须有时间窗口"
    assert "_LOGIN_MAX_FAILURES = 5" in auth_router, "登录失败限流必须设置失败次数上限"
    assert "HTTP_429_TOO_MANY_REQUESTS" in auth_router, "超过失败次数必须返回 429"
    assert "_record_failed_login(failure_key, now)" in auth_router, "失败登录必须被记录"
    assert "_clear_failed_login(failure_key)" in auth_router, "成功登录必须清理失败计数"


def check_dependency_reproducibility_contract() -> None:
    for line in _read("backend/requirements.txt").splitlines():
        requirement = line.strip()
        if not requirement or requirement.startswith("#") or requirement.startswith("-"):
            continue
        assert "==" in requirement, f"后端依赖必须固定版本：{requirement}"
    frontend_dockerfile = _read("frontend/Dockerfile")
    ci = _read(".github/workflows/ci.yml")
    assert "RUN npm ci" in frontend_dockerfile, "前端镜像必须使用 npm ci"
    assert "npm ci" in ci, "CI 前端依赖安装必须使用 npm ci"


def check_docs_current_product_names() -> None:
    for path in (
        "README.md",
        "backend/README.md",
        "frontend/README.md",
        "docs/Market数据采集中心-工程化落地方案.md",
    ):
        text = _read(path)
        for stale in ("情报中心", "线索池", "Task 1", "Task 2", "默认 http://localhost:3000", "营销数据驾驶舱", "Marketing Data Cockpit"):
            assert stale not in text, f"{path} 仍包含过期说法：{stale}"
        assert "市场洞察" in text, f"{path} 必须使用当前模块名"
    current_plan = _read("docs/Market数据采集中心-工程化落地方案.md")
    for stale in ("经营工作台", "营销平台", "marketing.your-domain.com"):
        assert stale not in current_plan, f"工程化落地方案不能保留旧整合路线：{stale}"
    for path in (
        "backend/app/main.py",
        "backend/app/schemas.py",
        "frontend/src/pages/User/Login/index.tsx",
        "frontend/src/layouts/EditorialLayout.tsx",
        "frontend/package.json",
    ):
        text = _read(path)
        for stale in ("咨询中心", "情报中心", "资讯中心", "线索池", "标讯池", "营销数据驾驶舱", "Marketing Data Cockpit"):
            assert stale not in text, f"{path} 仍包含旧模块名：{stale}"


def check_business_routes_require_auth() -> None:
    allowed_public = {"auth.py"}
    router_dir = ROOT / "backend/app/routers"
    for path in sorted(router_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            decorators = [ast.unparse(item) for item in node.decorator_list]
            route_decorators = [
                item for item in decorators
                if ".get(" in item or ".post(" in item or ".put(" in item or ".delete(" in item or ".patch(" in item
            ]
            if not route_decorators:
                continue
            if path.name in allowed_public or any("public_router" in item for item in route_decorators):
                continue
            source = ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""
            protected = (
                "require_permission" in source
                or "get_current_user" in source
                or "verify_api_key" in source
                or "verify_dingtalk_signature" in source
                or "dependencies=[Depends(verify_api_key)]" in "".join(route_decorators)
            )
            assert protected, f"{path}:{node.lineno} {node.name} 缺少访问控制"


def check_mutating_routes_use_business_permissions() -> None:
    contracts = {
        "backend/app/routers/reports.py": [
            'require_permission("reports:generate")',
            'require_permission("reports:view")',
        ],
        "backend/app/routers/express.py": [
            'require_permission("reports:generate")',
            'require_permission("reports:view")',
        ],
        "backend/app/routers/bidding_express.py": [
            'require_permission("management:express")',
            'require_permission("dashboard:view")',
        ],
        "backend/app/routers/opportunity_leads.py": [
            'require_permission("opportunities:view")',
            'require_permission("opportunities:manage")',
        ],
        "backend/app/routers/bot.py": [
            'require_permission("bot:view")',
            'require_permission("bot:configure")',
            'require_permission("bot:knowledge")',
            'require_permission("bot:approve")',
            'require_permission("bot:evaluate")',
            'require_permission("bot:broadcast")',
        ],
        "backend/app/permissions.py": [
            '"opportunities:manage"',
            '"bot:broadcast"',
        ],
    }
    for path, markers in contracts.items():
        text = _read(path)
        assert "get_current_user" not in text, f"{path} 不能只用登录态保护业务操作"
        for marker in markers:
            assert marker in text, f"{path} 缺少权限契约：{marker}"


def check_bot_enterprise_ops_contract() -> None:
    model = _read("backend/app/models.py")
    router = _read("backend/app/routers/bot.py")
    runtime = _read("backend/app/services/bot_runtime.py")
    frontend_api = _read_frontend_services()
    frontend_page = _read_frontend_page_tree("BotCenter")
    migration = _read("backend/migrations/versions/015_bot_enterprise_operations.py")
    sqlite_migration = (
        _read("backend/app/sqlite_auto_migration.py")
        + _read("backend/app/sqlite_bot_migration.py")
    )

    for class_name in (
        "BotChannelAdapter",
        "BotInboundEvent",
        "BotInboxItem",
        "BotHandoff",
        "BotTaskRun",
        "BotReleaseVersion",
        "BotFeedback",
        "BotKnowledgeSyncJob",
        "BotEnvironment",
        "BotCompliancePolicy",
    ):
        assert f"class {class_name}" in model, f"机器人运营模型缺少 {class_name}"
        assert class_name in runtime, f"机器人运行时缺少 {class_name}"

    for table_name in (
        "bot_channel_adapters",
        "bot_inbound_events",
        "bot_inbox_items",
        "bot_handoffs",
        "bot_task_runs",
        "bot_release_versions",
        "bot_feedback",
        "bot_knowledge_sync_jobs",
        "bot_environments",
        "bot_compliance_policies",
    ):
        assert table_name in migration, f"机器人运营迁移缺少 {table_name}"
        assert table_name in sqlite_migration, f"SQLite 自动迁移缺少 {table_name}"

    for route in (
        '"/channel-adapters"',
        '"/inbox"',
        '"/handoffs"',
        '"/task-runs"',
        '"/releases"',
        '"/feedback"',
        '"/knowledge-sync"',
        '"/environments"',
        '"/compliance-policies"',
        '"/observability-summary"',
    ):
        assert route in router, f"机器人中心缺少路由 {route}"

    for marker in (
        "fetchBotChannelAdapters",
        "fetchBotInbox",
        "createBotHandoff",
        "fetchBotReleases",
        "publishBotRelease",
        "fetchBotFeedback",
        "fetchBotKnowledgeSyncJobs",
        "fetchBotCompliancePolicies",
        "fetchBotObservabilitySummary",
    ):
        assert marker in frontend_api, f"前端 API 缺少 {marker}"
        assert marker in frontend_page, f"机器人中心页面未使用 {marker}"

    for label in ("生产运营", "发布观测", "合规环境", "知识同步任务", "多轮上下文"):
        assert label in frontend_page, f"机器人中心页面缺少 {label}"


def check_runtime_config_clear_contract() -> None:
    settings_router = _read("backend/app/routers/settings.py")
    assert 'if "webhook_url" in payload:' in settings_router, "钉钉 Webhook 必须支持清空保存"
    assert "row.webhook_url = encrypt_secret(webhook) if webhook else None" in settings_router, "空 Webhook 应写入 None，而不是保留旧值"


def check_runtime_url_validation_contract() -> None:
    validation = _read("backend/app/validation.py")
    llm_router = _read("backend/app/routers/llm_config.py")
    settings_router = _read("backend/app/routers/settings.py")
    crawler_config = _read("backend/app/routers/crawler_config.py")
    assert "def validate_http_url" in validation, "运行时外部 URL 必须走统一校验"
    assert "validate_http_url(payload.get(\"api_base_url\")" in llm_router, "LLM API Base URL 必须校验"
    assert "validate_http_url(webhook" in settings_router, "钉钉 Webhook URL 必须校验"
    assert "validate_http_url(payload.get(\"url\")" in crawler_config, "采集源 URL 必须校验"
    assert "validate_http_url(payload.get(\"base_url\")" in crawler_config, "采集源 Base URL 必须校验"


def check_intelligence_filter_contract() -> None:
    crawler_router = _read("backend/app/routers/crawler.py")
    assert "起始日期格式应为 YYYY-MM-DD" in crawler_router, "市场洞察起始日期格式错误不能静默忽略"
    assert "结束日期格式应为 YYYY-MM-DD" in crawler_router, "市场洞察结束日期格式错误不能静默忽略"
    assert "date.fromisoformat(start_date)" in crawler_router, "市场洞察必须按起始日期过滤发布日期"
    assert "date.fromisoformat(end_date)" in crawler_router, "市场洞察必须按结束日期过滤发布日期"


def check_password_policy_contract() -> None:
    auth = _read("backend/app/auth.py")
    users_router = _read("backend/app/routers/users.py")
    auth_router = _read("backend/app/routers/auth.py")
    management = _read_frontend_page_tree("Management")
    assert "PASSWORD_MIN_LENGTH = 8" in auth, "密码最小长度必须由后端公共常量定义"
    assert "PASSWORD_MIN_LENGTH" in users_router, "用户创建/重置必须使用统一密码策略"
    assert "PASSWORD_MIN_LENGTH" in auth_router, "本人修改密码必须使用统一密码策略"
    assert "min: 6" not in management, "管理后台不能保留 6 位密码校验"
    assert "至少6位" not in management, "管理后台不能保留 6 位密码提示"
    assert management.count("min: 8") >= 3, "管理后台三个密码入口必须至少 8 位"


def check_no_fake_demo_surfaces() -> None:
    main = _read("backend/app/main.py")
    preview = _read("backend/app/static/preview.html")
    assert "/bidding-demo" not in main, "不能保留无真实产物的标讯 demo 入口"
    assert "bidding_express_demo.html" not in main, "不能引用不存在的 demo 文件"
    assert "seed_demo.py" not in preview, "预览页不能提示不存在的数据脚本"
    assert "8000 端口" not in preview, "预览页不能保留旧端口提示"
    assert "Math.random" not in preview, "预览页不能生成随机展示值"


def check_clean_sqlite_bootstrap() -> None:
    script = """
import asyncio
import os
import sqlite3
from app.database import dispose_db, init_db
from app.main import _auto_migrate_sqlite

async def main():
    await init_db()
    _auto_migrate_sqlite()
    await dispose_db()

asyncio.run(main())
path = os.environ["DATABASE_URL"].replace("sqlite+aiosqlite:///", "")
conn = sqlite3.connect(path)
tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
required = {
    "activities", "staff", "crawler_items", "crawler_sources", "keyword_configs",
    "schedule_config", "system_users", "api_key_records", "dingtalk_configs",
    "opportunity_leads", "evidence_records", "intelligence_events",
    "crawler_task_locks", "crawler_task_runs", "report_pages",
    "department_weekly_reports", "bot_broadcasts",
    "bot_profiles", "bot_skills", "bot_conversations", "bot_messages",
    "bot_skill_runs", "bot_tool_calls", "bot_knowledge_files",
    "bot_knowledge_chunks", "bot_channel_bindings", "bot_test_cases",
    "bot_audit_logs", "bot_tasks", "bot_action_approvals",
    "bot_evaluation_runs", "bot_intent_corrections", "bot_collaboration_runs",
    "bot_channel_adapters", "bot_inbound_events", "bot_inbox_items",
    "bot_handoffs", "bot_task_runs", "bot_release_versions", "bot_feedback",
    "bot_knowledge_sync_jobs", "bot_environments", "bot_compliance_policies",
}
missing = sorted(required - tables)
conn.close()
if missing:
    raise SystemExit("missing tables: " + ",".join(missing))
"""
    with tempfile.NamedTemporaryFile(prefix="market-clean-", suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    for suffix in ("", "-shm", "-wal"):
        try:
            os.remove(db_path + suffix)
        except FileNotFoundError:
            pass
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    try:
        subprocess.run(
            [sys.executable, "-c", script],
            cwd=BACKEND,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        for suffix in ("", "-shm", "-wal"):
            try:
                os.remove(db_path + suffix)
            except FileNotFoundError:
                pass


def check_crawler_failure_message_contract() -> None:
    management = _read_frontend_page_tree("Management")
    assert "catch { message.error('采集失败'); }" not in management, "采集失败不能吞掉后端错误原因"
    assert "catch { message.error('测试失败'); }" not in management, "连接测试失败不能吞掉后端错误原因"
    assert "getApiErrorMessage(e, '采集失败')" in management, "采集失败需要展示后端错误原因"
    assert "getApiErrorMessage" in management, "管理后台需要统一展示接口错误原因"


def check_crawler_strategy_contract() -> None:
    seed_data = _read("backend/app/seed_data.py")
    policy = _read("backend/app/crawlers/policy.py")
    crawler_config = _read("backend/app/routers/crawler_config.py")
    crawler_router = _read("backend/app/routers/crawler.py")
    coverage = _read("backend/scripts/crawler_coverage_acceptance.py")
    api = _read_frontend_services()
    management = _read_frontend_page_tree("Management")
    for marker in (
        "complete_crawler_source_rules",
        "dynamic_public_html_probe_v1",
        "bidding_public_list_v1",
        "amount_rule_profile",
    ):
        assert marker in seed_data, f"默认源头缺少可执行规则补齐契约：{marker}"
    for marker in (
        "SOURCE_TIER_PROFILES",
        "build_source_strategy_profile",
        "strategy_sort_rank",
        "stop_rules",
        "operator_action",
    ):
        assert marker in policy, f"爬虫策略层缺少结构化字段：{marker}"
    for marker in (
        "build_source_strategy_profile",
        "\"source_tier\"",
        "\"strategy_status\"",
        "\"strategy_gaps\"",
        "\"strategy_sort_rank\"",
        "\"rule_profile\"",
        "\"rule_status\"",
    ):
        assert marker in crawler_config, f"采集源接口缺少策略返回字段：{marker}"
    for marker in (
        "\"rule_profile\"",
        "\"rule_note\"",
    ):
        assert marker in crawler_router, f"运行状态接口缺少采集规则返回字段：{marker}"
    for marker in (
        "source_tier?:",
        "strategy_status?:",
        "strategy_sort_rank?:",
        "stop_rules?:",
        "rule_profile?:",
    ):
        assert marker in api, f"前端 API 类型缺少策略字段：{marker}"
    for marker in (
        "来源等级",
        "策略状态",
        "SOURCE_RULE_PROFILE_LABELS",
        "sourceStrategyTooltip",
        "strategy_sort_rank",
    ):
        assert marker in management, f"管理后台缺少策略展示或排序：{marker}"
    assert "check_all_sources_have_executable_rules" in coverage, "验收脚本必须阻止无采集规则的来源进入源池"


def check_crawler_item_archive_contract() -> None:
    crawler_router = _read("backend/app/routers/crawler.py")
    assert "@crawler_router.delete(\"/items/{item_id}\")" in crawler_router, "爬虫数据管理必须保留兼容归档入口"
    assert "item.is_invalid = True" in crawler_router, "单条爬虫数据删除入口必须改为归档"
    assert ".values(is_invalid=True" in crawler_router, "批量爬虫数据删除入口必须改为归档"
    assert "db.delete(item)" not in crawler_router, "爬虫数据不能物理删除，否则会破坏证据链"
    assert "delete(CrawlerItem)" not in crawler_router, "爬虫数据不能批量物理删除"


def check_api_error_message_contract() -> None:
    for path in (
        "backend/app/routers/reports.py",
        "backend/app/routers/express.py",
        "backend/app/routers/bidding_express.py",
    ):
        text = _read(path)
        assert "detail=str(exc)" not in text, f"{path} 不能把内部异常原文直接返回给前端"
        assert "report generation failed: {exc}" not in text, f"{path} 不能暴露英文内部异常"
        assert "str(exc)[:200]" not in text, f"{path} 不能截断后透传内部异常"
    assert "logger.exception(\"report generation failed" in _read("backend/app/routers/reports.py"), "报告生成失败必须写后端日志"
    assert "logger.exception(\"daily express generation failed" in _read("backend/app/routers/express.py"), "速递生成失败必须写后端日志"


def check_frontend_management_tone() -> None:
    layout = _read("frontend/src/layouts/EditorialLayout.tsx")
    management = _read_frontend_page_tree("Management")
    assert "format('DDD')" not in layout, "页眉期号不能依赖未启用的 day-of-year 格式"
    assert "format('YYYYMMDD')" in layout, "页眉期号必须使用稳定日期格式"
    assert "getPermissionLabel(p)" in management, "管理页角色矩阵必须展示业务权限名称"
    assert "r.permissions.map(p => <Tag key={p} style={{ fontSize: 10 }}>{p}</Tag>)" not in management, "管理页不能直接展示内部权限码"
    for path in (
        "frontend/src/pages/Dashboard/index.tsx",
        "frontend/src/pages/Management/index.tsx",
        "frontend/src/pages/Intelligence/index.tsx",
        "frontend/src/pages/Opportunities/index.tsx",
        "frontend/src/pages/OpportunityRadar/index.tsx",
    ):
        if path.startswith("frontend/src/pages/"):
            page = path.split("/")[3]
            text = _read_frontend_page_tree(page)
        else:
            text = _read(path)
        for marker in ("✅", "⚠️"):
            assert marker not in text, f"{path} 不应使用临时符号化提示：{marker}"
        for marker in ("后续接", "待接入", "未实现"):
            assert marker not in text, f"{path} 不应向管理者展示内部建设口径：{marker}"
    express_router = _read("backend/app/routers/express.py")
    assert "长图截图已保存" not in express_router, "钉钉推送不能暴露服务器本地截图路径"


def check_frontend_permission_gates() -> None:
    api = _read_frontend_services()
    layout = _read("frontend/src/layouts/EditorialLayout.tsx")
    dashboard = _read_frontend_page_tree("Dashboard")
    intelligence = _read_frontend_page_tree("Intelligence")
    lead_review = _read("frontend/src/pages/OpportunityRadar/index.tsx")
    assert "userHasPermission" in api, "前端必须有统一权限判断函数"
    assert "canAccessPath" in layout and "management:view" in layout, "导航必须按权限控制管理入口"
    assert "canGenerateReports" in dashboard and "canManageExpress" in dashboard, "看板写操作按钮必须按权限控制"
    assert "canRunAgents" in intelligence and "management:crawler" in intelligence, "市场洞察 Agent 运行必须按权限控制"
    assert "canManageLeads" in lead_review and "opportunities:manage" in lead_review, "线索确认写操作必须按权限控制"


def check_external_links_are_noopener() -> None:
    for path in sorted((ROOT / "frontend/src").rglob("*.tsx")):
        text = path.read_text(encoding="utf-8")
        if "window.open" not in text:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if "window.open" in line and "'_blank'" in line and "noopener,noreferrer" not in line:
                raise AssertionError(f"{path.relative_to(ROOT)}:{line_number} 外部链接缺少 noopener,noreferrer")


def check_html_preview_is_sandboxed() -> None:
    dashboard = _read_frontend_page_tree("Dashboard")
    assert "function sanitizeHtmlForPreview" in dashboard, "报告 HTML 预览必须先清理脚本和事件属性"
    assert "container.innerHTML = sanitizeHtmlForPreview" in dashboard, "转图片临时渲染不能直接写入原始 HTML"
    assert 'sandbox=""' in dashboard, "报告预览 iframe 必须启用 sandbox"
    assert "srcDoc={sanitizeHtmlForPreview" in dashboard, "报告预览 iframe 不能直接加载原始 HTML"


def check_department_weekly_archive_contract() -> None:
    model = _read("backend/app/models.py")
    reports_router = _read("backend/app/routers/reports.py")
    api = _read_frontend_services()
    dashboard = _read_frontend_page_tree("Dashboard")
    migration = _read("backend/migrations/versions/011_department_weekly_reports.py")
    assert "class DepartmentWeeklyReport" in model, "部门周报必须有独立归档模型"
    assert "MAX_DEPARTMENT_WEEKLY_HTML_BYTES = 8 * 1024 * 1024" in reports_router, "HTML 周报上传必须限制大小"
    assert '@router.post("/department-weekly/upload")' in reports_router, "缺少部门周报上传接口"
    assert 'require_permission("reports:generate")' in reports_router, "部门周报上传/删除必须使用报告生成权限"
    assert 'require_permission("reports:view")' in reports_router, "部门周报列表/详情必须使用报告查看权限"
    assert 'endswith((".html", ".htm"))' in reports_router, "部门周报上传必须限制 HTML/HTM 文件"
    assert "text_content=_extract_text_content(html)" in reports_router, "部门周报必须抽取文本用于后续总结"
    assert "fetchDepartmentWeeklyReports" in api and "uploadDepartmentWeeklyReport" in api, "前端服务层缺少部门周报接口"
    assert "部门周报归档" in dashboard and "title=\"部门周报预览\"" in dashboard, "日报周报页面缺少部门周报归档预览"
    assert "srcDoc={sanitizeHtmlForPreview(departmentWeeklyPreview.html_content)}" in dashboard, "部门周报预览必须走净化函数"
    assert "department_weekly_reports" in migration, "缺少部门周报数据库迁移"


def check_opportunity_center_boundary_contract() -> None:
    center = _read("frontend/src/pages/Opportunities/index.tsx")
    radar = _read("frontend/src/pages/OpportunityRadar/index.tsx")
    assert "fetchOpportunityLeads" in center, "商机中心必须读取后端已确认线索，不能只展示静态卡片"
    assert "fetchActivities" in center, "商机中心必须读取日报活动证据"
    assert "已接入证据源" in center, "商机中心应展示真实证据来源数量"
    assert "缺少销售侧契约" in center, "商机中心未接销售侧机制时必须明确边界"
    assert "预测数据源" not in center, "商机中心不能把未接入预测做成指标"
    assert "待接入" not in center, "商机中心不能保留像功能入口的待接入文案"
    assert "商机中心待接入区" not in radar, "标讯线索确认不能指向不存在的商机待接入区"


def check_database_migration_contract() -> None:
    env = _read("backend/migrations/env.py")
    main = _read("backend/app/main.py")
    assert "Alembic migrations are PostgreSQL-only" in env, "Alembic 对 SQLite 必须明确失败"
    assert '@app.get("/api/ready"' in main, "后端必须提供 readiness 探针"
    assert "await conn.execute(text(\"SELECT 1\"))" in main, "readiness 必须真实检查数据库"
    for path in sorted((ROOT / "backend/migrations/versions").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert 'SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"' in text, f"{path.name} 不能硬编码 schema"
    assert not (ROOT / "backend/seed_demo.py").exists(), "不能保留旧 demo seed 脚本"

    migration_env = os.environ.copy()
    migration_env.update({
        "DATABASE_URL": "postgresql+asyncpg://market:secret@localhost:5432/market",
        "DATABASE_SCHEMA": "codex_schema_check",
    })
    rendered = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=BACKEND,
        env=migration_env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert rendered.returncode == 0, rendered.stderr
    assert "CREATE TABLE codex_schema_check.staff" in rendered.stdout, "PostgreSQL 迁移 SQL 必须使用配置 schema"
    assert "016_aipaas_config_and_crawler_item_flags" in rendered.stdout, "PostgreSQL 迁移 SQL 必须覆盖最新迁移"


def check_ci_contract() -> None:
    ci = _read(".github/workflows/ci.yml")
    for marker in (
        "python-version: \"3.9\"",
        "python -m compileall backend/app backend/scripts backend/migrations",
        "python backend/scripts/engineering_acceptance.py",
        "python backend/scripts/unit_contracts.py",
        "python backend/scripts/business_acceptance.py",
        "python backend/scripts/crawler_coverage_acceptance.py",
        "npm ci",
        "npm run tsc -- --noEmit",
        "npm run build",
        "npm audit --audit-level=high --omit=dev --registry=https://registry.npmjs.org --fetch-retries=5 --fetch-timeout=60000",
    ):
        assert marker in ci, f"CI 缺少验收步骤：{marker}"


def check_frontend_proxy_contract() -> None:
    umirc = _read("frontend/.umirc.ts")
    readme = _read("frontend/README.md")
    assert "API_PROXY_TARGET" in umirc, "前端开发代理不能硬编码后端地址"
    assert "target: apiProxyTarget" in umirc, "三个开发代理入口必须复用同一个目标"
    assert "API_PROXY_TARGET" in readme, "前端 README 必须说明开发代理覆盖方式"


def check_market_snapshot_fixture_contract() -> None:
    fixture_path = ROOT / "backend/app/fixtures/market_snapshot.json"
    assert fixture_path.exists(), "必须提交脱敏采集配置与市场数据快照"
    snapshot = json.loads(fixture_path.read_text(encoding="utf-8"))
    counts = snapshot.get("metadata", {}).get("counts", {})
    assert counts.get("crawler_sources", 0) >= 100, "快照必须包含已配置采集源"
    assert counts.get("crawler_items", 0) >= 300, "快照必须包含已抓取市场信号"
    assert counts.get("opportunity_leads", 0) >= 90, "快照必须包含已识别标讯线索"
    assert counts.get("evidence_records") == counts.get("crawler_items"), "证据记录数量必须与采集信号对齐"
    text = fixture_path.read_text(encoding="utf-8")
    for pattern in (
        re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
        re.compile(r"\bding[a-z0-9]{12,}\b", re.IGNORECASE),
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    ):
        assert not pattern.search(text), "快照不能包含疑似真实外部平台凭证"
    assert "content_excerpt" in text and '"content":' not in text, "快照只能提交摘录，不能提交第三方全文字段"
    assert "seed-snapshot" in _read("deploy/marketctl.sh"), "部署工具必须提供快照导入命令"

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "snapshot.db"
        env = {
            **os.environ,
            "PYTHONPATH": str(BACKEND),
            "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}",
        }
        imported = subprocess.run(
            [sys.executable, "backend/scripts/import_market_snapshot.py", "--fixture", str(fixture_path)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert imported.returncode == 0, imported.stderr
        imported_counts = json.loads(imported.stdout)
        assert imported_counts["crawler_items"] == counts["crawler_items"], "快照导入必须恢复全部市场信号"


def run_check(name: str, fn: Callable[[], None]) -> bool:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL {name}: {exc}")
        return False
    print(f"PASS {name}")
    return True


def main() -> int:
    checks = [
        ("长任务超时契约", check_long_task_timeout_contract),
        ("默认上传 Key 不生效", check_default_upload_key_is_not_active),
        ("运行时密钥加密契约", check_secret_store_contract),
        ("Webhook 加密存储", check_webhook_url_is_encrypted),
        ("钉钉应用身份契约", check_dingtalk_identity_contract),
        ("AIPAAS 同步闭环", check_aipaas_sync_contract),
        ("浏览器会话 Cookie 契约", check_browser_session_cookie_contract),
        ("登录失败限流契约", check_login_rate_limit_contract),
        ("依赖可复现契约", check_dependency_reproducibility_contract),
        ("产品文档命名同步", check_docs_current_product_names),
        ("业务路由访问控制", check_business_routes_require_auth),
        ("写操作业务权限", check_mutating_routes_use_business_permissions),
        ("机器人生产运营契约", check_bot_enterprise_ops_contract),
        ("运行时配置清空闭环", check_runtime_config_clear_contract),
        ("运行时 URL 校验", check_runtime_url_validation_contract),
        ("市场洞察筛选契约", check_intelligence_filter_contract),
        ("统一密码策略", check_password_policy_contract),
        ("无虚假 Demo 入口", check_no_fake_demo_surfaces),
        ("干净 SQLite 启动", check_clean_sqlite_bootstrap),
        ("采集失败原因可见", check_crawler_failure_message_contract),
        ("采集运行保护契约", check_crawler_runtime_guard_contract),
        ("爬虫策略分级契约", check_crawler_strategy_contract),
        ("爬虫数据归档契约", check_crawler_item_archive_contract),
        ("接口错误信息收敛", check_api_error_message_contract),
        ("前端管理语气", check_frontend_management_tone),
        ("前端权限入口", check_frontend_permission_gates),
        ("外链打开安全", check_external_links_are_noopener),
        ("HTML 预览隔离", check_html_preview_is_sandboxed),
        ("部门周报归档契约", check_department_weekly_archive_contract),
        ("商机中心边界", check_opportunity_center_boundary_contract),
        ("公开 HTML 响应头", check_public_html_response_contract),
        ("容器部署契约", check_container_deploy_contract),
        ("公网部署工具包契约", check_public_deployment_toolkit_contract),
        ("数据库迁移契约", check_database_migration_contract),
        ("CI 验收契约", check_ci_contract),
        ("前端代理契约", check_frontend_proxy_contract),
        ("采集快照入仓契约", check_market_snapshot_fixture_contract),
    ]
    passed = sum(1 for name, fn in checks if run_check(name, fn))
    print(f"\n{passed}/{len(checks)} engineering checks passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
