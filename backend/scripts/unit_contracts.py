"""Fast unit-level contracts for core business helpers.

These checks intentionally avoid network calls and database writes. They cover
small but fragile rules that can regress even when the larger acceptance suite
still starts successfully.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from fastapi import HTTPException  # noqa: E402

from app.crawlers.ai_crawler import AICrawler, _keyword_match  # noqa: E402
from app.crawlers.intelligence_agent import build_intelligence_profile  # noqa: E402
from app.routers.dingtalk_robot import _extract_text_message, _verify_dingtalk_signature  # noqa: E402
from app.secret_store import decrypt_secret, encrypt_secret, is_encrypted_secret  # noqa: E402
from app.services.dingtalk_service import (  # noqa: E402
    normalize_custom_robot_secret,
    validate_custom_robot_webhook_url,
)


def check_industry_keyword_boundaries() -> None:
    title = "How GPT-5 helped immunologist solve a 3-year-old mystery"
    hits, score = _keyword_match(title, "")
    assert hits == ["gpt"], hits
    assert score == 30, score
    assert AICrawler._classify_ai_topic(title) == "llm"
    profile = build_intelligence_profile(kind="ai", title=title, matched_keywords=hits)
    assert "空间数据" not in profile["topics"], profile

    for spatial_title, expected_hit in (
        ("GDAL 3.13.0 is released", "gdal"),
        ("PROJ 9.8.1 is released", "proj"),
        ("QGIS and PostGIS geospatial workflow", "qgis"),
        ("空间数据治理平台建设方案", "空间数据"),
    ):
        spatial_hits, _ = _keyword_match(spatial_title, "")
        assert expected_hit in [item.lower() for item in spatial_hits], spatial_hits
        assert AICrawler._classify_ai_topic(spatial_title) == "spatial_ai", spatial_title


def check_dingtalk_signature_and_text() -> None:
    secret = "SEC-unit-contract-secret"
    timestamp = str(int(time.time() * 1000))
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}\n{secret}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sign = base64.b64encode(digest).decode("utf-8")
    _verify_dingtalk_signature(timestamp, sign, secret)
    _verify_dingtalk_signature(timestamp, quote_plus(sign), secret)

    try:
        _verify_dingtalk_signature(timestamp, "bad-sign", secret)
    except HTTPException as exc:
        assert exc.status_code == 401
    else:  # pragma: no cover - defensive contract
        raise AssertionError("bad DingTalk signature was accepted")

    message = _extract_text_message({
        "msgtype": "text",
        "senderStaffId": "staff-001",
        "senderNick": "Alice",
        "text": {"content": "日报：拜访市局客户，推进空间数据治理项目。"},
    })
    assert message["user_id"] == "staff-001"
    assert message["user_name"] == "Alice"
    assert message["content"] == "拜访市局客户，推进空间数据治理项目。"


def check_dingtalk_webhook_validation() -> None:
    valid = "https://oapi.dingtalk.com/robot/send?access_token=abc"
    assert validate_custom_robot_webhook_url(valid) == valid
    assert validate_custom_robot_webhook_url("", allow_empty=True) == ""
    assert normalize_custom_robot_secret(" SECabc ") == "SECabc"
    for invalid in (
        "http://oapi.dingtalk.com/robot/send?access_token=abc",
        "https://example.com/robot/send?access_token=abc",
        "https://oapi.dingtalk.com/robot/send",
    ):
        try:
            validate_custom_robot_webhook_url(invalid)
        except ValueError:
            pass
        else:  # pragma: no cover - defensive contract
            raise AssertionError(f"invalid webhook accepted: {invalid}")


def check_secret_roundtrip() -> None:
    encrypted = encrypt_secret("unit-secret-value")
    assert encrypted and encrypted.startswith("enc:v2:")
    assert is_encrypted_secret(encrypted)
    assert decrypt_secret(encrypted) == "unit-secret-value"
    assert decrypt_secret("legacy-plaintext") == "legacy-plaintext"
    assert encrypt_secret(encrypted) == encrypted


def run_check(name: str, fn) -> bool:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL {name}: {exc}")
        return False
    print(f"PASS {name}")
    return True


def main() -> int:
    checks = [
        ("industry keyword boundaries", check_industry_keyword_boundaries),
        ("dingtalk signature and text", check_dingtalk_signature_and_text),
        ("dingtalk webhook validation", check_dingtalk_webhook_validation),
        ("secret roundtrip", check_secret_roundtrip),
    ]
    passed = sum(1 for name, fn in checks if run_check(name, fn))
    print(f"\n{passed}/{len(checks)} unit contracts passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
