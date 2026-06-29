#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'USAGE'
Market 数据采集中心一键部署

最简单用法:
  bash install.sh

也可以一次填好域名和邮箱:
  bash install.sh --domain market.company.com --email ops@company.com

参数:
  --domain 域名     公网访问域名，例如 market.company.com
  --email 邮箱      HTTPS 证书通知邮箱
  --force           重新生成 .env，旧 .env 会自动备份
  --no-seed         不导入内置采集配置和市场数据快照
  -h, --help        查看帮助
USAGE
}

domain="${MARKET_DOMAIN:-}"
email="${ACME_EMAIL:-}"
force="false"
seed_snapshot="true"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      domain="${2:-}"
      shift 2
      ;;
    --email)
      email="${2:-}"
      shift 2
      ;;
    --force)
      force="true"
      shift
      ;;
    --no-seed)
      seed_snapshot="false"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
  esac
done

need_command() {
  local name="$1"
  local hint="$2"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "缺少 $name。$hint" >&2
    exit 1
  fi
}

need_command docker "请先在服务器安装 Docker。"
if ! docker compose version >/dev/null 2>&1; then
  echo "缺少 Docker Compose 插件。请安装 Docker 官方版本，或升级 Docker。" >&2
  exit 1
fi

if [[ -z "$domain" && -t 0 ]]; then
  read -r -p "请输入公网域名，例如 market.company.com: " domain
fi
if [[ -z "$email" && -t 0 ]]; then
  read -r -p "请输入 HTTPS 证书通知邮箱: " email
fi

if [[ -z "$domain" || -z "$email" ]]; then
  echo "还缺少域名或邮箱。你可以这样执行: bash install.sh --domain market.company.com --email ops@company.com" >&2
  exit 1
fi

echo "开始一键部署 Market 数据采集中心。"
echo "部署域名: $domain"

"$ROOT/deploy/marketctl.sh" doctor

init_args=(init --domain "$domain" --email "$email")
if [[ "$force" == "true" ]]; then
  init_args+=(--force)
fi

"$ROOT/deploy/marketctl.sh" "${init_args[@]}"
"$ROOT/deploy/marketctl.sh" up
if [[ "$seed_snapshot" == "true" ]]; then
  "$ROOT/deploy/marketctl.sh" seed-snapshot
  "$ROOT/deploy/marketctl.sh" smoke
fi

cat <<EOF

部署完成。

访问地址:
  https://$domain

管理员账号:
  用户名: admin
  密码: 查看服务器项目目录 .env 文件里的 ADMIN_PASSWORD

以后更新新版本:
  ./deploy/marketctl.sh update

查看运行状态:
  ./deploy/marketctl.sh status
EOF
