#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "开始更新 Market 数据采集中心。更新前会自动备份数据库。"
exec "$ROOT/deploy/marketctl.sh" update "$@"
