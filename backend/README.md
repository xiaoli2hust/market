# 营销智能管理平台 · 后端

基于 FastAPI + PostgreSQL + 通义千问 (DashScope OpenAI 兼容) 的后端服务，
负责钉钉聊天 JSON 接收、营销动作抽取、活动/人员查询，以及钉钉机器人推送等能力。

> 本目录是 Task 1 重写后的项目骨架，仅含可运行的最小结构，业务逻辑由后续任务填充。

## 目录结构

```
market/backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # pydantic-settings 配置
│   ├── database.py          # 异步引擎 + Session + Base
│   ├── auth.py              # JWT / bcrypt / 上传 Key 工具
│   ├── models.py            # ORM 模型（Task 2 填充）
│   ├── schemas.py           # 通用 Pydantic 基类与占位
│   ├── routers/             # 路由骨架：auth / import_data / activities / staff
│   └── services/
│       └── llm_service.py   # 通义千问客户端封装
├── migrations/              # Alembic 迁移
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── alembic.ini
├── requirements.txt
├── Dockerfile
└── .env.example
```

## 本地开发

```bash
cd market/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env  # 按需修改

# 启动开发服务（要求本地 PostgreSQL 已就绪，schema=marketing）
uvicorn app.main:app --reload --port 8000
```

启动后访问：

- 健康检查：<http://localhost:8000/api/health>
- Swagger：<http://localhost:8000/api/docs>

## 数据库迁移

```bash
# 生成新迁移（基于 app.models 的最新 metadata）
alembic revision --autogenerate -m "describe change"

# 应用迁移
alembic upgrade head
```

> Alembic 使用同步 `psycopg2` 驱动，运行时 FastAPI 使用 `asyncpg` 异步驱动；
> `migrations/env.py` 会自动把 `postgresql+asyncpg://` 重写为 `postgresql+psycopg2://`。

## Docker

```bash
docker build -t market-backend .
docker run --rm -p 8000:8000 --env-file .env market-backend
```

镜像基于 `mcr.microsoft.com/playwright/python:v1.49.0-noble`，预装 Chromium，
便于后续在同一镜像中扩展 RPA / 爬虫任务。

## 环境变量

详见 [.env.example](./.env.example)。关键变量：

| 变量 | 说明 |
| --- | --- |
| `DATABASE_URL` | asyncpg 连接串 |
| `DATABASE_SCHEMA` | 业务 schema，默认 `marketing` |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | 通义千问 OpenAI 兼容接口 |
| `DINGTALK_WEBHOOK_URL` / `DINGTALK_SECRET` | 钉钉机器人推送 |
| `JWT_*` / `ADMIN_*` | 后台登录鉴权 |
| `UPLOAD_API_KEY` | 内网 RPA / 爬虫推送鉴权 |

## 后续任务

- Task 2：补全 `app/models.py` 与初始 Alembic 迁移；
- Task 3：实现 JSON 导入 + LLM 抽取闭环；
- Task 4：完善登录/活动/人员业务接口与前端联调。
