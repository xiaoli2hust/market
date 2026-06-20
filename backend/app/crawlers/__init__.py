"""爬虫引擎模块。

提供：
- BaseCrawler 基类与 CrawlResult 数据类
- 数据处理流水线（去重、评分、摘要）
- 具体爬虫实现（市场动态、竞对监控、AI资讯）
- 爬虫配置（关键词库、目标站点）
"""

from .base import BaseCrawler, CrawlResult, CrawlStats

__all__ = ["BaseCrawler", "CrawlResult", "CrawlStats"]
