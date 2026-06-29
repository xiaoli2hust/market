# Market 数据采集中心 · 前端

前端基于 **@umijs/max + React 18 + TypeScript + Ant Design 5 + ProComponents**，提供四个一级模块：

- 日报周报
- 市场洞察
- 商机中心
- 管理中心

## 本地启动

```bash
cd /Users/xiaoli/Documents/market/frontend
npm install
npm run dev -- --host 127.0.0.1 --port 8002
```

开发态代理默认指向 `http://127.0.0.1:8001`，可通过 `API_PROXY_TARGET` 覆盖：

```bash
API_PROXY_TARGET=http://127.0.0.1:9001 npm run dev -- --host 127.0.0.1 --port 8002
```

- `/api` → `http://127.0.0.1:8001`
- `/r` → `http://127.0.0.1:8001`
- `/re` → `http://127.0.0.1:8001`

## 路由

| 路径 | 说明 |
| --- | --- |
| `/user/login` | 登录页 |
| `/dashboard` | 日报周报 |
| `/intelligence` | 市场洞察 |
| `/intelligence/opportunities` | 标讯线索确认 |
| `/opportunities` | 商机中心 |
| `/management` | 管理中心 |

## 工程约束

- 页面面向经营管理者，不展示调试话术。
- 长耗时动作使用长任务请求超时，避免后端仍在运行但前端误报失败。
- 管理中心配置必须真实影响后端链路；未接入能力需明确标注。
- 市场洞察不是原始列表，必须呈现分析、证据和行动建议。

## 主要目录

```text
frontend/
├── .umirc.ts
├── src/
│   ├── app.tsx
│   ├── layouts/
│   ├── pages/
│   ├── components/
│   ├── services/
│   ├── constants/
│   └── global.less
└── package.json
```
