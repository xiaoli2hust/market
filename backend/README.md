# Market 数据采集中心 · 后端

FastAPI 后端负责四条主链路：

- 日报周报：日报 JSON 接收、LLM 解析、活动查询、报告生成与推送。
- 市场洞察：标讯、政策、市场、竞对、行业知识采集，证据记录、情报事件和 Agent 周/月分析。
- 商机中心：标讯线索识别、人工确认、状态流转，后续承接销售侧商机机制。
- 管理中心：采集源、关键词、调度、LLM、Prompt、用户、API Key、钉钉和结构化标讯配置。

## 本地启动

默认使用本地 SQLite，适合零配置试用：

```bash
cd /Users/xiaoli/Documents/market-product/backend
pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

启动后访问：

- 健康检查：<http://127.0.0.1:8001/api/health>
- Swagger：<http://127.0.0.1:8001/api/docs>

SQLite 模式下应用启动会自动创建缺失表，并补齐必要的本地迁移字段。生产或多人环境请使用 PostgreSQL + Alembic。

## 数据库迁移

PostgreSQL 部署使用 Alembic：

```bash
cd /Users/xiaoli/Documents/market-product/backend
python3 -m alembic upgrade head
```

Alembic 迁移链只面向 PostgreSQL。SQLite 是本地单机试用模式，由应用启动时自动建表和补齐兼容字段。

迁移链当前包含：

- 基础经营表
- 商机线索表
- 爬虫运行日志
- 管理中心运行配置
- 加密字段长度扩展
- 报告版本生命周期
- 情报证据、情报事件、爬虫任务锁和任务运行实例

## Docker

项目根目录提供 `docker-compose.yml`。先复制根目录 `.env.example` 为 `.env`，填入强密码和随机密钥。后端镜像启动时会先校验生产密钥，再执行：

```bash
python3 -m alembic upgrade head
```

然后启动 FastAPI 服务。Compose 中的数据库密码、`JWT_SECRET_KEY`、`SECRET_ENCRYPTION_KEY`、`ADMIN_PASSWORD` 和 `UPLOAD_API_KEY` 均为必填项，不能使用默认弱口令。

## 关键环境变量

| 变量 | 说明 |
| --- | --- |
| `DATABASE_URL` | 默认 SQLite；生产建议 `postgresql+asyncpg://...` |
| `DATABASE_SCHEMA` | PostgreSQL schema，默认 `marketing` |
| `JWT_SECRET_KEY` | 登录与公开报告 token 签名密钥 |
| `SECRET_ENCRYPTION_KEY` | 运行时密钥加密材料，生产必须稳定配置 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 初始管理员账号，仅用于首次启动 |
| `UPLOAD_API_KEY` | 兼容旧导入链路；占位值不会被视为有效 Key |

LLM、Prompt、钉钉、结构化标讯账号、采集源和关键词属于运行时配置，应优先在管理中心维护。
