"""JSON 数据导入路由。

负责接收内网 RPA / 钉钉机器人推送的聊天日报 JSON：
1. 落地原始 JSON 到 ``daily_report_files``（同 user_id+date 去重更新）；
2. 拼接 ``conversations.question`` 作为日报原文；
3. 自动创建 staff（默认角色"销售"）；
4. 调用通义千问解析为结构化活动并落 ``activities`` 表；
5. 解析失败不阻塞文件落库，状态写入 parse_status / error_message。

接口受 ``verify_api_key`` 保护，期望 Header：``Authorization: Bearer <管理中心生成的 API Key>``。
"""

from __future__ import annotations

import logging
from datetime import date as date_cls
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_api_key
from ..database import get_db
from ..models import Activity, DailyReportFile, Staff
from ..schemas import ImportJsonRequest, ImportJsonResponse
from ..services.llm_service import parse_daily_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/import", tags=["import"])


def _parse_date(raw: str) -> date_cls:
    """宽松解析日期字符串。"""

    raw = (raw or "").strip()
    if not raw:
        raise ValueError("date is required")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    # 兜底：直接 fromisoformat（容忍带时间）
    return datetime.fromisoformat(raw).date()


def _build_report_text(payload: ImportJsonRequest) -> str:
    """从 conversations.question 拼接日报原文。"""

    chunks: list[str] = []
    for item in payload.conversations:
        question = (item.question or "").strip()
        if not question:
            continue
        chunks.append(question)
    return "\n\n".join(chunks)


async def _get_or_create_staff(db: AsyncSession, user_name: str) -> Staff:
    """根据 user_name 查找或创建 staff。"""

    name = (user_name or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_name is required",
        )

    result = await db.execute(select(Staff).where(Staff.name == name))
    staff = result.scalar_one_or_none()
    if staff is not None:
        return staff

    staff = Staff(name=name, role="销售", department="", is_active=True)
    db.add(staff)
    await db.flush()
    logger.info("自动创建 staff：name=%s id=%s", name, staff.id)
    return staff


async def _upsert_report_file(
    db: AsyncSession,
    *,
    user_id: str,
    user_name: str,
    file_date: date_cls,
    raw_content: dict[str, Any],
) -> DailyReportFile:
    """同 user_id + date 去重 upsert，返回最终持久化的记录。"""

    file_name = f"{user_id}_{file_date.isoformat()}.json"
    stmt = select(DailyReportFile).where(
        DailyReportFile.user_id == user_id,
        DailyReportFile.file_date == file_date,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is None:
        record = DailyReportFile(
            user_id=user_id,
            user_name=user_name,
            file_name=file_name,
            file_date=file_date,
            raw_content=raw_content,
            parse_status="pending",
        )
        db.add(record)
        await db.flush()
        return record

    existing.user_name = user_name
    existing.file_name = file_name
    existing.raw_content = raw_content
    existing.parse_status = "pending"
    existing.parsed_at = None
    existing.error_message = None
    await db.flush()
    return existing


@router.post(
    "/chat-json",
    response_model=ImportJsonResponse,
    dependencies=[Depends(verify_api_key)],
    summary="接收机器人推送的聊天日报 JSON",
)
async def import_chat_json(
    request: ImportJsonRequest,
    db: AsyncSession = Depends(get_db),
) -> ImportJsonResponse:
    """接收内网机器人推送的聊天记录 JSON 并解析落库。"""

    try:
        file_date = _parse_date(request.date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid date: {exc}",
        ) from exc

    raw_payload: dict[str, Any] = request.model_dump(mode="json")

    # 1. 原始文件落库（去重 upsert）
    report_file = await _upsert_report_file(
        db,
        user_id=request.user_id,
        user_name=request.user_name,
        file_date=file_date,
        raw_content=raw_payload,
    )

    # 2. staff 查找/创建
    staff = await _get_or_create_staff(db, request.user_name)

    # 同一员工同一天的日报事实只能以最后一次导入结果为准。
    await db.execute(
        delete(Activity).where(
            Activity.staff_id == staff.id,
            Activity.report_date == file_date,
        )
    )

    # 3. 拼接日报原文
    report_text = _build_report_text(request)

    activities_count = 0
    parse_status = "success"
    error_message: str | None = None

    if not report_text:
        parse_status = "empty"
        error_message = "conversations 为空或 question 字段全为空"
        logger.warning(
            "日报原文为空：user=%s date=%s", request.user_name, file_date.isoformat()
        )
    else:
        # 4. 调 LLM 解析
        try:
            activities = await parse_daily_report(
                user_name=request.user_name,
                report_text=report_text,
                db=db,
            )
        except Exception as exc:  # noqa: BLE001 - LLM 服务已内部兜底，这里再加一道保险
            logger.exception("LLM 解析异常：%s", exc)
            activities = []
            parse_status = "failed"
            error_message = f"llm error: {exc}"

        if activities:
            for item in activities:
                db.add(
                    Activity(
                        staff_id=staff.id,
                        report_date=file_date,
                        activity_type=item["activity_type"],
                        target=item.get("target"),
                        opportunity=item.get("opportunity"),
                        description=item.get("description"),
                        confidence=float(item.get("confidence") or 0.8),
                        is_reviewed=False,
                        source_file_id=report_file.id,
                    )
                )
            activities_count = len(activities)
        else:
            if parse_status == "success":
                parse_status = "failed"
                error_message = error_message or "LLM 未返回任何活动（可能未配置 Key 或解析失败）"

    # 6. 更新解析状态
    report_file.parse_status = parse_status
    report_file.parsed_at = datetime.now(tz=timezone.utc)
    report_file.error_message = error_message

    await db.commit()
    await db.refresh(report_file)

    return ImportJsonResponse(
        file_id=report_file.id,
        parse_status=report_file.parse_status,
        activities_count=activities_count,
        message=error_message,
    )
