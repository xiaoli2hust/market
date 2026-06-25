"""爬虫引擎模块。

提供：
- BaseCrawler 基类与 CrawlResult 数据类
- BaseCrawler 内置去重、相关性阈值和入库统计
- 具体爬虫实现（标讯雷达、政策研判、市场线索、竞对监控、行业知识）
- 爬虫配置（关键词库、目标站点）
"""

from .base import BaseCrawler, CrawlResult, CrawlStats

__all__ = ["BaseCrawler", "CrawlResult", "CrawlStats"]
