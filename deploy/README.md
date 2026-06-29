# Market 数据采集中心 · 内网部署与公网发布

生产部署使用 `deploy/docker-compose.prod.yml`：

- 只发布 `gateway` 的 `80/443`。
- `frontend`、`backend`、`db` 均不发布宿主机端口。
- Caddy 自动申请 HTTPS 证书。
- 后端启动前会先校验生产密钥，再执行 Alembic 迁移。

## 小白一键部署

在项目根目录执行：

```bash
bash install.sh
```

按提示填写公网域名和证书邮箱即可。脚本会自动完成：

- 服务器自检。
- 生成强密码和密钥。
- 安全与质量门禁。
- 构建并启动数据库、后端、前端和网关。
- 导入仓库内置的采集源、关键词和脱敏市场数据快照。
- 冒烟验证登录、健康检查、管理接口、采集状态和日报同步配置入口。

也可以一次填好：

```bash
bash install.sh --domain market.company.com --email ops@company.com
```

后续更新新版本：

```bash
bash deploy/update.sh
```

这条命令会先备份数据库，再跑安全与质量门禁，通过后自动替换服务。

## 部署自检与冒烟

部署前检查服务器：

```bash
./deploy/marketctl.sh doctor
```

部署后验证服务：

```bash
./deploy/marketctl.sh smoke
```

如果使用内网自签证书或 Caddy 内部证书：

```bash
./deploy/marketctl.sh smoke --insecure
```

## 第一次部署

```bash
./deploy/marketctl.sh init --domain market.company.com --email ops@company.com
```

执行后会自动生成根目录 `.env`：

- 自动生成数据库密码、登录密钥、运行时密钥、初始管理员密码和上传 Key。
- 自动写入 `MARKET_DOMAIN`、`ACME_EMAIL` 和 `CORS_ORIGINS`。
- 自动运行公网安全门禁。

然后：

```bash
./deploy/marketctl.sh gate
./deploy/marketctl.sh up
```

如需把仓库内置的脱敏采集源、关键词和已抓取市场数据导入生产库：

```bash
./deploy/marketctl.sh seed-snapshot
```

## 后续更新

把新代码覆盖到服务器项目目录后执行：

```bash
./deploy/marketctl.sh update
```

更新流程会先做数据库备份，再跑质量门禁，再重新构建并替换容器。

## 常用命令

```bash
./deploy/marketctl.sh status
./deploy/marketctl.sh logs
./deploy/marketctl.sh smoke
./deploy/marketctl.sh seed-snapshot
./deploy/marketctl.sh backup
./deploy/marketctl.sh pack
```

## 防火墙建议

公网只开放：

- TCP 80
- TCP 443

不要开放：

- PostgreSQL 5432
- 后端 8000
- 前端容器 80
