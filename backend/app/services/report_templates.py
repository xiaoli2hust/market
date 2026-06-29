"""HTML templates for report generation."""

from __future__ import annotations

_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    color: #1a1714; background: #f5efe3; line-height: 1.6;
    -webkit-font-smoothing: antialiased;
}
.report { max-width: 680px; margin: 0 auto; background: #faf6ec; }

/* Masthead */
.masthead {
    background: #1a1714; color: #faf6ec; padding: 28px 24px 20px;
    position: relative; overflow: hidden;
}
.masthead::after {
    content: ''; position: absolute; bottom: 0; left: 0; right: 0;
    height: 4px; background: #C53A2C;
}
.masthead-eyebrow {
    font-size: 11px; letter-spacing: 0.22em; text-transform: uppercase;
    color: rgba(250,246,236,0.6); margin-bottom: 8px;
}
.masthead-title {
    font-size: 26px; font-weight: 800; line-height: 1.2; margin-bottom: 6px;
}
.masthead-title .accent { color: #C53A2C; }
.masthead-meta {
    display: flex; justify-content: space-between; align-items: flex-end;
    margin-top: 12px; padding-top: 12px;
    border-top: 1px solid rgba(250,246,236,0.15);
}
.masthead-date { font-size: 14px; font-weight: 600; }
.masthead-issue { font-size: 11px; color: rgba(250,246,236,0.5); letter-spacing: 0.12em; }

/* Stats bar */
.stats-bar {
    display: flex; background: #1a1714; padding: 0;
}
.stat-cell {
    flex: 1; text-align: center; padding: 14px 8px;
    border-right: 1px solid rgba(250,246,236,0.1);
}
.stat-cell:last-child { border-right: none; }
.stat-num {
    font-size: 28px; font-weight: 800; color: #C53A2C;
    font-family: Georgia, 'Times New Roman', serif;
}
.stat-label {
    font-size: 10px; color: rgba(250,246,236,0.5);
    letter-spacing: 0.12em; text-transform: uppercase; margin-top: 2px;
}

/* Content sections */
.content { padding: 0 24px; }
.section {
    padding: 20px 0; border-bottom: 1px dashed rgba(26,23,20,0.15);
}
.section:last-child { border-bottom: none; }
.section-head {
    display: flex; align-items: center; gap: 8px; margin-bottom: 14px;
}
.section-num {
    font-size: 11px; font-weight: 700; color: #C53A2C;
    font-family: Georgia, serif; letter-spacing: 0.06em;
}
.section-title {
    font-size: 16px; font-weight: 700; color: #1a1714;
}

/* AI Summary */
.summary-block {
    background: #fff; border-left: 4px solid #C53A2C;
    padding: 16px 18px; margin-bottom: 4px; border-radius: 0 4px 4px 0;
}
.summary-text {
    font-size: 14px; line-height: 1.9; color: #3b342d;
    white-space: pre-wrap;
}

/* Note */
.note-block {
    background: rgba(197,58,44,0.06); border: 1px dashed rgba(197,58,44,0.3);
    padding: 12px 16px; margin-top: 12px; border-radius: 4px;
    font-size: 13px; color: #3b342d; line-height: 1.7;
}
.note-label {
    font-size: 11px; font-weight: 700; color: #C53A2C;
    letter-spacing: 0.1em; margin-bottom: 4px;
}

/* Staff group */
.staff-group { margin-bottom: 18px; }
.staff-header {
    display: flex; align-items: center; gap: 10px; margin-bottom: 10px;
}
.staff-seal {
    width: 32px; height: 32px; background: #C53A2C; color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; font-weight: 700; border-radius: 2px;
    font-family: Georgia, serif;
}
.staff-name { font-size: 15px; font-weight: 700; color: #1a1714; }
.staff-dept { font-size: 12px; color: #7a6f62; margin-left: 4px; }
.staff-count {
    font-size: 11px; color: #7a6f62; margin-left: auto;
    font-family: Georgia, serif;
}

/* Activity items */
.activity-list { list-style: none; }
.activity-item {
    display: flex; gap: 10px; padding: 8px 12px;
    margin-bottom: 4px; background: #fff; border-radius: 4px;
    border: 1px solid rgba(26,23,20,0.06);
    transition: box-shadow 0.15s;
}
.activity-item:hover { box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.activity-dot {
    width: 8px; height: 8px; border-radius: 50%;
    margin-top: 6px; flex-shrink: 0;
}
.activity-body { flex: 1; min-width: 0; }
.activity-type {
    font-size: 11px; font-weight: 600; letter-spacing: 0.04em;
    display: inline-block; margin-bottom: 2px;
}
.activity-target {
    font-size: 12px; color: #7a6f62; margin-left: 8px;
}
.activity-desc {
    font-size: 13px; color: #3b342d; line-height: 1.6; margin-top: 2px;
}
.activity-opp {
    display: inline-block; font-size: 11px; color: #A8482A;
    background: rgba(168,72,42,0.08); padding: 1px 8px;
    border-radius: 10px; margin-top: 4px;
}

/* Weekly extras */
.trend-chart {
    display: flex; align-items: flex-end; gap: 6px;
    height: 80px; padding: 8px 0;
}
.trend-bar-wrap {
    flex: 1; display: flex; flex-direction: column;
    align-items: center; gap: 4px;
}
.trend-bar {
    width: 100%; max-width: 36px; background: #C53A2C;
    border-radius: 2px 2px 0 0; min-height: 4px;
    transition: height 0.3s;
}
.trend-label {
    font-size: 10px; color: #7a6f62;
    font-family: Georgia, serif;
}
.trend-count {
    font-size: 10px; color: #1a1714; font-weight: 700;
}

/* Ranking */
.rank-list { list-style: none; }
.rank-item {
    display: flex; align-items: center; gap: 12px;
    padding: 8px 0; border-bottom: 1px dashed rgba(26,23,20,0.1);
}
.rank-item:last-child { border-bottom: none; }
.rank-num {
    font-size: 18px; font-weight: 800; color: #C53A2C;
    font-family: Georgia, serif; width: 28px; text-align: center;
}
.rank-num.top { color: #C53A2C; }
.rank-name { font-size: 14px; font-weight: 600; flex: 1; }
.rank-bar-wrap {
    width: 120px; height: 6px; background: rgba(26,23,20,0.08);
    border-radius: 3px; overflow: hidden;
}
.rank-bar {
    height: 100%; background: #C53A2C; border-radius: 3px;
}
.rank-count {
    font-size: 12px; color: #7a6f62;
    font-family: Georgia, serif; width: 40px; text-align: right;
}

/* Footer */
.footer {
    text-align: center; padding: 20px 24px;
    border-top: 1px solid rgba(26,23,20,0.1);
    background: #f5efe3;
}
.footer-text {
    font-size: 11px; color: #7a6f62; letter-spacing: 0.08em;
}
.footer-line {
    font-size: 10px; color: rgba(122,111,98,0.6); margin-top: 4px;
}

@media print {
    body { background: #fff; }
    .report { box-shadow: none; }
}
"""
