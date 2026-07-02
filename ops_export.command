#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_FILE="$ROOT/backend/market.db"

if [[ ! -f "$DB_FILE" ]]; then
  echo "没有找到本地采集数据库：$DB_FILE"
  echo "请先在本机系统里完成采集，再重新双击这个文件。"
  read -r -p "按回车关闭窗口..."
  exit 1
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
if [[ -d "$HOME/Desktop" ]]; then
  OUT_ROOT="$HOME/Desktop"
else
  OUT_ROOT="$ROOT/releases"
fi

PACKAGE_NAME="Market-ops-delivery-$STAMP"
PACKAGE_DIR="$OUT_ROOT/$PACKAGE_NAME"
ZIP_FILE="$OUT_ROOT/$PACKAGE_NAME.zip"

mkdir -p "$PACKAGE_DIR"

echo "正在生成给运维的交付包，请稍等..."
python3 "$ROOT/backend/scripts/export_market_snapshot.py" \
  --db "$DB_FILE" \
  --output "$PACKAGE_DIR/market_snapshot.json" \
  > "$PACKAGE_DIR/snapshot_metadata.json"

cat > "$PACKAGE_DIR/README-老板看这个.txt" <<'TXT'
你只需要做一件事：

把这个 zip 压缩包发给运维。

包里已经包含你本地采集好的市场数据快照，不包含本机密码、API Key、钉钉密钥和数据库文件。
TXT

cat > "$PACKAGE_DIR/README-运维导入说明.txt" <<'TXT'
Market 数据采集快照导入说明

这个包来自业务负责人本机，包含：
- market_snapshot.json：脱敏后的采集源、关键词、调度配置、市场数据、证据记录、情报事件、标讯线索
- snapshot_metadata.json：快照数量统计

不包含：
- .env
- 本地 SQLite 数据库
- API Key / 密码 / 钉钉密钥
- 上传周报 HTML 原文
- 第三方网页全文

内网服务器导入步骤：

1. 解压这个 zip。
2. 进入服务器上的 market 项目目录。
3. 执行：

   ./deploy/marketctl.sh seed-snapshot /解压目录/market_snapshot.json

说明：
- 这个导入是幂等的，重复执行不会重复堆数据。
- 导入前请确保服务已经通过 ./deploy/marketctl.sh up 启动。
- 密钥类配置需要部署后在管理中心单独配置。
TXT

if command -v ditto >/dev/null 2>&1; then
  rm -f "$ZIP_FILE"
  ditto -c -k --sequesterRsrc --keepParent "$PACKAGE_DIR" "$ZIP_FILE"
elif command -v zip >/dev/null 2>&1; then
  rm -f "$ZIP_FILE"
  (cd "$OUT_ROOT" && zip -qr "$ZIP_FILE" "$PACKAGE_NAME")
else
  echo "没有找到压缩工具，已生成文件夹：$PACKAGE_DIR"
  open "$OUT_ROOT" >/dev/null 2>&1 || true
  read -r -p "按回车关闭窗口..."
  exit 0
fi

echo ""
echo "完成。"
echo "你只需要把这个文件发给运维："
echo "$ZIP_FILE"
echo ""
open "$OUT_ROOT" >/dev/null 2>&1 || true
read -r -p "按回车关闭窗口..."
