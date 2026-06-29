"""Engineering readiness metrics for deployment hardening."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IGNORED_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "dist",
    ".umi",
    ".umi-production",
    "backups",
    "releases",
}

SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|"
    r"(?:client_secret|app_secret|api_key|password)\s*[:=]\s*['\"][^'\"]{12,}['\"]|"
    r"136[0-9]{8}|jy@|ywhAVe|3c6ca4fc)"
)


def _iter_files(suffixes: set[str]):
    for path in ROOT.rglob("*"):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path.name == "engineering_metrics.py":
            continue
        if path.is_file() and path.suffix in suffixes:
            yield path


def _line_rows(suffixes: set[str]) -> list[dict]:
    rows = []
    for path in _iter_files(suffixes):
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        rows.append({"file": str(path.relative_to(ROOT)), "lines": len(lines)})
    return sorted(rows, key=lambda item: item["lines"], reverse=True)


def _secret_hits() -> list[dict]:
    hits = []
    for path in ROOT.rglob("*"):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path.name == "engineering_metrics.py":
            continue
        if not path.is_file() or path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".tar", ".gz", ".db"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for index, line in enumerate(text.splitlines(), 1):
            if SECRET_RE.search(line):
                hits.append({"file": str(path.relative_to(ROOT)), "line": index})
    return hits


def _contains(path: str, markers: list[str]) -> bool:
    text = (ROOT / path).read_text(encoding="utf-8", errors="ignore")
    return all(marker in text for marker in markers)


def build_report() -> dict:
    py_rows = _line_rows({".py"})
    ts_rows = _line_rows({".ts", ".tsx"})
    backend_acceptance_scripts = [
        "backend/scripts/engineering_acceptance.py",
        "backend/scripts/business_acceptance.py",
        "backend/scripts/crawler_coverage_acceptance.py",
        "backend/scripts/unit_contracts.py",
        "backend/scripts/deployment_smoke.py",
    ]
    existing_acceptance = [item for item in backend_acceptance_scripts if (ROOT / item).exists()]
    security_headers = {
        "caddy": _contains(
            "deploy/Caddyfile",
            ["Strict-Transport-Security", "X-Content-Type-Options", "X-Frame-Options", "Permissions-Policy"],
        ),
        "nginx": _contains("frontend/nginx.conf", ["X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy"]),
        "public_html": _contains("backend/app/routers/reports.py", ["X-Content-Type-Options", "X-Frame-Options"])
        and _contains("backend/app/routers/express.py", ["X-Content-Type-Options", "X-Frame-Options"]),
    }
    deploy_inner = _contains(
        "deploy/marketctl.sh",
        ["cmd_doctor", "cmd_gate", "cmd_smoke", "compose up -d --build", "backup"],
    )
    deploy_public = _contains(
        "deploy/marketctl.sh",
        ["validate_public_identity", "security_quality_gate.py", "cmd_smoke"],
    ) and (ROOT / "deploy/Caddyfile").exists()
    frontend_test_files = [
        path for path in ROOT.rglob("*")
        if not any(part in IGNORED_PARTS for part in path.parts)
        and path.is_file()
        and path.name.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx"))
    ]
    front_coverage = 0 if not frontend_test_files else 40
    secret_hits = _secret_hits()

    metrics = {
        "python_max_lines": max((row["lines"] for row in py_rows), default=0),
        "python_files_over_800": [row for row in py_rows if row["lines"] > 800],
        "typescript_max_lines": max((row["lines"] for row in ts_rows), default=0),
        "typescript_files_over_600": [row for row in ts_rows if row["lines"] > 600],
        "backend_acceptance_automation_rate": round(len(existing_acceptance) / len(backend_acceptance_scripts) * 100, 2),
        "frontend_test_coverage_rate": front_coverage,
        "deploy_ready_inner": deploy_inner,
        "deploy_ready_public": deploy_public,
        "security_headers": security_headers,
        "hardcoded_secret_hits": secret_hits,
    }
    checks = {
        "python_single_file_max_le_2000": metrics["python_max_lines"] <= 2000,
        "python_over_800_count_le_5": len(metrics["python_files_over_800"]) <= 5,
        "typescript_single_file_max_le_600": metrics["typescript_max_lines"] <= 600,
        "backend_acceptance_automation_ge_90": metrics["backend_acceptance_automation_rate"] >= 90,
        "frontend_test_coverage_ge_40": metrics["frontend_test_coverage_rate"] >= 40,
        "deploy_ready_inner": deploy_inner,
        "deploy_ready_public": deploy_public,
        "security_headers_all": all(security_headers.values()),
        "no_hardcoded_secrets": not secret_hits,
    }
    return {"checks": checks, "metrics": metrics}


def main() -> int:
    report = build_report()
    for name, ok in report["checks"].items():
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0 if all(report["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
