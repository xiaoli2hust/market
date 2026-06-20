# 营销数据驾驶舱 · 前端

基于 **@umijs/max + React 18 + TypeScript + Ant Design 5 + ProComponents**。

视觉方向（Editorial Business Intelligence）：
- 主色：朱砂红 `#C53A2C`，背景：暖米白 `#F5EFE3`，墨色：`#1A1714`
- 字体：Noto Serif SC（标题/数字）+ Noto Sans SC（正文）

## 启动

```bash
cd market/frontend
npm install
npm run dev   # 默认 http://localhost:3000
```

开发态会将 `/api` 代理到 `http://localhost:8000`（FastAPI 后端）。

## 路由

| 路径 | 说明 |
| --- | --- |
| `/user/login` | 登录页 |
| `/dashboard` | 日报周报（主页） |

## 核心模块

```
src/
├── .umirc.ts            # 应用配置/代理/路由/主题
├── src/
│   ├── app.tsx          # 运行时配置 + 鉴权拦截
│   ├── layouts/
│   │   └── EditorialLayout.tsx
│   ├── pages/
│   │   ├── User/Login/index.tsx
│   │   └── Dashboard/index.tsx
│   ├── components/
│   │   └── StaffDetailDrawer.tsx
│   ├── services/
│   │   └── api.ts
│   ├── constants/
│   │   └── actionTypes.ts
│   └── global.less
```
