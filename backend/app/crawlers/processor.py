"""数据处理流水线：LLM 摘要生成、相关度评分增强。

当前版本使用关键词匹配评分 + 文本截取摘要。
后续可接入 LLM 提升质量。
"""

from __future__ import annotations

import logging

from .config import CRAWLER_RELEVANCE_THRESHOLD

logger = logging.getLogger(__name__)


def truncate_summary(text: str, max_length: int = 100) -> str:
    """截取文本作为摘要。"""

    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit("，", 1)[0].rsplit(",", 1)[0] + "…"


def is_relevant(score: float | None, threshold: float | None = None) -> bool:
    """判断相关度是否达标。"""

    if score is None:
        return True  # 未评分的保留
    return score >= (threshold or CRAWLER_RELEVANCE_THRESHOLD)
