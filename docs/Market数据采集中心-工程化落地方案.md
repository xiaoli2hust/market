# Market 数据采集中心 · 工程化落地方案

## 1. 产品边界

Market 数据采集中心面向 G 端销售与市场团队，核心目标是把外部信号、团队动作和商机跟进沉淀为可追踪、可复盘、可预测的经营证据。

当前产品边界分为四个中心：

- 日报周报：服务管理者掌握部门每天在做什么，生成日报、周报、标讯速递和推送。
- 市场洞察：采集并分析标讯、政策、市场线索、竞对动态和行业知识。
- 商机中心：承接已确认线索，服务销售跟进、机器人追问、签单预测和回款预测；不强行混入市场采集逻辑。
- 管理中心：维护采集源、关键词、调度、模型、Prompt、账号、API Key、钉钉和结构化标讯数据源配置。

## 2. 核心链路

```text
外部信号采集
  -> 结构化入库
  -> AI 相关性评分与事件归类
  -> 标讯/政策/竞对/行业分析
  -> 高相关线索确认
  -> 商机中心承接销售侧跟进
  -> 日报周报面向管理者复盘
```

平台不把“采集到数据”当成结果。采集只是第一步，真正的 Agent 价值在于按周、按月识别变化：哪些行业升温、哪些关键词触发最多、哪些客户/区域值得跟进、哪些竞对动作需要响应。

## 3. Agent 分工

### 3.1 标讯雷达 Agent

输入：结构化标讯接口、白名单公共资源网站、管理后台关键词。

输出：

- 高贴合度标讯关注清单。
- 行业分布、区域分布、关键词触发分布。
- 金额抽取、采购单位、公告类型和时间排序。
- 可转商机线索。

### 3.2 政策与市场跟踪 Agent

输入：政策网站、政数/公安/大数据/电力/运营商/空间智能/Agent 相关公开信息。

输出：

- 自然年政策跟踪。
- 周/月市场导向分析。
- 可行动建议：重点区域、重点行业、重点客户类型。

### 3.3 竞对监控 Agent

输入：超图、中地数码、航天宏图、武大吉奥、京东舆图、海致等竞对公开新闻、案例、产品和中标信息。

输出：

- 竞对客户动作。
- 产品方案变化。
- 区域扩张信号。
- 合作、招聘、资质、标准和案例事件。

### 3.4 行业知识 Agent

输入：空间智能、GIS、数字孪生、数据治理、Agent、行业研究与公开技术动态。

输出：

- 行业知识补充。
- 趋势摘要。
- 对标讯/政策/市场线索的解释背景。

## 4. 工程架构

```text
Frontend (Umi/React)
  -> Nginx / Dev Proxy
  -> FastAPI Backend
  -> PostgreSQL (生产) / SQLite (本机试用)
  -> Crawler Scheduler
  -> Runtime Config Store
  -> External Sources
```

生产环境使用 PostgreSQL + Alembic。SQLite 只用于本机试用，由应用启动时自动建表和补齐兼容字段。

## 5. 安全与配置

- 浏览器登录主链路使用 HttpOnly Cookie，前端不保存 JWT。
- 登录失败 15 分钟窗口内超过 5 次会被限流。
- 生产部署必须显式配置强密钥：数据库密码、`JWT_SECRET_KEY`、`SECRET_ENCRYPTION_KEY`、`ADMIN_PASSWORD`、`UPLOAD_API_KEY`。
- LLM、Prompt、钉钉、结构化标讯账号、采集源和关键词属于运行时配置，应在管理中心维护。
- API Key 只在创建时展示一次，数据库中以不可逆哈希保存。
- Webhook、模型 Key、结构化标讯账号等运行时密钥加密入库。

## 6. 爬虫合规策略

- 所有公开网页采集默认低频请求、统一 User-Agent、失败退避、尊重 robots。
- 不绕过验证码、不绕过登录、不做高并发扫描。
- 无解析规则的网站只能作为候选源，不默认启用。
- 标讯主链路优先走授权结构化接口，其他公共站点必须通过白名单和解析规则审核。
- 采集失败要记录来源、原因、时间和运行批次，供管理中心追溯。

## 7. 部署

根目录提供 `docker-compose.yml`。复制 `.env.example` 为 `.env` 后填写强密码和随机密钥。

本地试用：

```bash
cd /Users/xiaoli/Documents/market/backend
pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

cd /Users/xiaoli/Documents/market/frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 8002
```

生产部署：

```bash
docker compose --env-file .env config
docker compose --env-file .env up -d --build
```

如果生产入口使用 HTTPS，应将 `AUTH_COOKIE_SECURE=true`。

## 8. 验收

当前项目固化了三类验收脚本：

- `python3 backend/scripts/engineering_acceptance.py`
- `python3 backend/scripts/business_acceptance.py`
- `python3 backend/scripts/crawler_coverage_acceptance.py`

前端必须通过：

- `npm run tsc -- --noEmit`
- `npm run build`

数据库必须通过：

- SQLite 模式拒绝 Alembic 迁移，改由本机启动自举。
- PostgreSQL 模式可生成完整 Alembic SQL。

## 9. 当前外部限制

容器实际启动依赖本机 Docker daemon。若 daemon 未启动，只能完成 Compose 配置解析和离线迁移验证，不能完成真实容器运行验证。
