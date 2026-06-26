#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${MARKET_ENV_FILE:-$ROOT/.env}"
PROD_COMPOSE="$ROOT/deploy/docker-compose.prod.yml"
BACKUP_DIR="$ROOT/backups"
RELEASE_DIR="$ROOT/releases"

compose() {
  docker compose --env-file "$ENV_FILE" -f "$PROD_COMPOSE" "$@"
}

usage() {
  cat <<'USAGE'
Market 数据采集中心部署工具

用法:
  ./deploy/marketctl.sh init --domain 域名 --email 邮箱
                                  初始化 .env，自动生成随机密钥并写入公网访问配置
  ./deploy/marketctl.sh gate        运行安全与质量门禁
  ./deploy/marketctl.sh up          首次构建并启动生产服务
  ./deploy/marketctl.sh seed-snapshot 导入仓库内置的脱敏采集源与市场数据快照
  ./deploy/marketctl.sh update      备份数据库、运行门禁、重建并替换服务
  ./deploy/marketctl.sh backup      备份 PostgreSQL 数据库
  ./deploy/marketctl.sh restore FILE 从备份 SQL 恢复数据库
  ./deploy/marketctl.sh status      查看服务状态
  ./deploy/marketctl.sh logs        查看服务日志
  ./deploy/marketctl.sh down        停止服务
  ./deploy/marketctl.sh pack        生成可拷贝到服务器的一键部署包
USAGE
}

require_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "缺少 ${ENV_FILE}。先执行: ./deploy/marketctl.sh init" >&2
    exit 1
  fi
}

generate_secret() {
  python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
}

validate_public_identity() {
  local domain="$1"
  local email="$2"
  python3 - "$domain" "$email" <<'PY'
import ipaddress
import re
import sys

domain = (sys.argv[1] or "").strip().lower().strip(".")
email = (sys.argv[2] or "").strip().lower()
errors = []

if domain.startswith(("http://", "https://")):
    errors.append("域名只填写主机名，不要带 http:// 或 https://")
if any(marker in domain for marker in ("localhost", "example", "your-domain", "yourdomain")):
    errors.append("域名不能使用示例值、localhost 或 your-domain")
if domain.endswith((".local", ".invalid", ".test", ".localhost")):
    errors.append("域名必须是公网域名，不能使用 .local/.invalid/.test")
try:
    ipaddress.ip_address(domain)
    errors.append("公网 HTTPS 部署必须使用域名，不能直接使用 IP")
except ValueError:
    pass
if not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", domain):
    errors.append("域名格式不正确，例如 market.company.com")

if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
    errors.append("证书邮箱格式不正确")
if "example" in email or "your" in email:
    errors.append("证书邮箱不能使用示例邮箱")

if errors:
    print("公网配置不完整：", file=sys.stderr)
    for item in errors:
        print(f"- {item}", file=sys.stderr)
    raise SystemExit(1)
PY
}

replace_env_value() {
  local key="$1"
  local value="$2"
  python3 - "$ENV_FILE" "$key" "$value" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines()
prefix = f"{key}="
for index, line in enumerate(lines):
    if line.startswith(prefix):
        lines[index] = f"{key}={value}"
        break
else:
    lines.append(f"{key}={value}")
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

cmd_init() {
  local domain="${MARKET_DOMAIN:-}"
  local email="${ACME_EMAIL:-}"
  local force="false"

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
      -h|--help)
        echo "用法: ./deploy/marketctl.sh init --domain market.company.com --email ops@company.com [--force]"
        return
        ;;
      *)
        echo "未知 init 参数: $1" >&2
        echo "用法: ./deploy/marketctl.sh init --domain market.company.com --email ops@company.com" >&2
        exit 1
        ;;
    esac
  done

  if [[ -z "$domain" && -t 0 ]]; then
    read -r -p "请输入公网域名（例如 market.company.com）: " domain
  fi
  if [[ -z "$email" && -t 0 ]]; then
    read -r -p "请输入 HTTPS 证书通知邮箱: " email
  fi
  validate_public_identity "$domain" "$email"

  if [[ -f "$ENV_FILE" ]]; then
    if [[ "$force" != "true" ]]; then
      echo ".env 已存在，不覆盖。"
      echo "如需重新生成，请执行: ./deploy/marketctl.sh init --domain $domain --email $email --force"
      return
    fi
    mkdir -p "$BACKUP_DIR"
    local stamp
    stamp="$(date +%Y%m%d-%H%M%S)"
    cp "$ENV_FILE" "$BACKUP_DIR/env-$stamp.bak"
    echo "已备份旧 .env: $BACKUP_DIR/env-$stamp.bak"
  fi
  cp "$ROOT/deploy/env.production.example" "$ENV_FILE"
  replace_env_value MARKET_DOMAIN "$domain"
  replace_env_value ACME_EMAIL "$email"
  replace_env_value CORS_ORIGINS "[\"https://$domain\"]"
  replace_env_value POSTGRES_PASSWORD "$(generate_secret)"
  replace_env_value JWT_SECRET_KEY "$(generate_secret)"
  replace_env_value SECRET_ENCRYPTION_KEY "$(generate_secret)"
  replace_env_value ADMIN_PASSWORD "$(generate_secret)"
  replace_env_value UPLOAD_API_KEY "$(generate_secret)"
  chmod 600 "$ENV_FILE"
  python3 "$ROOT/backend/scripts/security_quality_gate.py" --env "$ENV_FILE" --profile public
  echo ".env 已生成并通过安全门禁。请妥善保存 ADMIN_PASSWORD 和 ${ENV_FILE}。"
}

cmd_gate() {
  require_env
  python3 "$ROOT/backend/scripts/security_quality_gate.py" --env "$ENV_FILE" --profile public

  python3 -m compileall "$ROOT/backend/app" "$ROOT/backend/scripts" "$ROOT/backend/migrations"
  python3 "$ROOT/backend/scripts/engineering_acceptance.py"
  python3 "$ROOT/backend/scripts/business_acceptance.py"
  python3 "$ROOT/backend/scripts/crawler_coverage_acceptance.py"

  (cd "$ROOT/frontend" && npm ci && npm run tsc -- --noEmit && npm run build)
  compose config >/dev/null
}

cmd_up() {
  require_env
  cmd_gate
  compose up -d --build
  compose ps
}

cmd_seed_snapshot() {
  require_env
  compose exec -T backend python scripts/import_market_snapshot.py
}

cmd_backup() {
  require_env
  mkdir -p "$BACKUP_DIR"
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
  local stamp
  stamp="$(date +%Y%m%d-%H%M%S)"
  local target="$BACKUP_DIR/market-db-$stamp.sql"
  compose exec -T db pg_dump -U "${POSTGRES_USER:-market}" "${POSTGRES_DB:-market}" > "$target"
  gzip -f "$target"
  echo "数据库备份完成: $target.gz"
}

cmd_restore() {
  require_env
  local file="${1:-}"
  if [[ -z "$file" || ! -f "$file" ]]; then
    echo "请指定存在的 SQL 或 SQL.GZ 备份文件。" >&2
    exit 1
  fi
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
  if [[ "$file" == *.gz ]]; then
    gzip -dc "$file" | compose exec -T db psql -U "${POSTGRES_USER:-market}" "${POSTGRES_DB:-market}"
  else
    compose exec -T db psql -U "${POSTGRES_USER:-market}" "${POSTGRES_DB:-market}" < "$file"
  fi
  echo "数据库恢复完成。"
}

cmd_update() {
  require_env
  cmd_backup || {
    echo "备份失败，已停止更新。" >&2
    exit 1
  }
  cmd_gate
  compose up -d --build --remove-orphans
  compose ps
}

cmd_status() {
  require_env
  compose ps
}

cmd_logs() {
  require_env
  compose logs -f --tail=200
}

cmd_down() {
  require_env
  compose down
}

cmd_pack() {
  mkdir -p "$RELEASE_DIR"
  local stamp
  stamp="$(date +%Y%m%d-%H%M%S)"
  local target="$RELEASE_DIR/market-product-$stamp.tar.gz"
  tar \
    --exclude='.git' \
    --exclude='.env' \
    --exclude='.runtime' \
    --exclude='backups' \
    --exclude='releases' \
    --exclude='frontend/node_modules' \
    --exclude='frontend/dist' \
    --exclude='frontend/src/.umi' \
    --exclude='frontend/src/.umi-production' \
    --exclude='frontend/src/.umi-test' \
    --exclude='frontend/.umi' \
    --exclude='frontend/.umi-production' \
    --exclude='frontend/.umi-test' \
    --exclude='backend/market.db' \
    --exclude='backend/market.db-*' \
    --exclude='*.db' \
    --exclude='*.db-shm' \
    --exclude='*.db-wal' \
    --exclude='*.sqlite' \
    --exclude='*.sqlite3' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.log' \
    --exclude='.DS_Store' \
    --exclude='output' \
    -czf "$target" \
    -C "$ROOT/.." "$(basename "$ROOT")"
  echo "部署包已生成: $target"
}

case "${1:-}" in
  init) shift; cmd_init "$@" ;;
  gate) cmd_gate ;;
  up) cmd_up ;;
  seed-snapshot) cmd_seed_snapshot ;;
  update) cmd_update ;;
  backup) cmd_backup ;;
  restore) shift; cmd_restore "${1:-}" ;;
  status) cmd_status ;;
  logs) cmd_logs ;;
  down) cmd_down ;;
  pack) cmd_pack ;;
  -h|--help|help|"") usage ;;
  *)
    echo "未知命令: $1" >&2
    usage
    exit 1
    ;;
esac
