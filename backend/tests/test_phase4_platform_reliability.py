"""Phase 4C：平台级错误分类补全测试。

覆盖 classify_adapter_error 新增的 upstream_blocked / invalid_manifest / unknown_error，
以及既有 login_required / adapter_missing / adapter_error 不回归。
"""
from app.collectors.bb_browser_runtime import (
    ERR_ADAPTER_ERROR,
    ERR_ADAPTER_MISSING,
    ERR_INVALID_MANIFEST,
    ERR_LOGIN_REQUIRED,
    ERR_UNKNOWN_ERROR,
    ERR_UPSTREAM_BLOCKED,
    classify_adapter_error,
)


def test_login_required_not_regressed():
    assert classify_adapter_error({"error": "401 Unauthorized"}) == ERR_LOGIN_REQUIRED
    assert classify_adapter_error({"error": "需要登录"}) == ERR_LOGIN_REQUIRED
    assert classify_adapter_error("please login") == ERR_LOGIN_REQUIRED


def test_adapter_missing_not_regressed():
    assert classify_adapter_error({"error": "adapter not found"}) == ERR_ADAPTER_MISSING
    assert classify_adapter_error({"error": "module not found"}) == ERR_ADAPTER_MISSING


def test_adapter_error_generic_not_regressed():
    # 含 adapter/timeout/error 的普通 adapter 错误仍归类 adapter_error（不落到 unknown_error）
    assert classify_adapter_error({"error": "timeout in adapter"}) == ERR_ADAPTER_ERROR
    assert classify_adapter_error({"error": "adapter exit code 1"}) == ERR_ADAPTER_ERROR


def test_baidu_failed_to_fetch_is_upstream_blocked():
    # Phase 3A 现场：百度风控的原始错误 TypeError: Failed to fetch
    assert (
        classify_adapter_error(
            {"error": {"message": "TypeError: Failed to fetch"}}
        )
        == ERR_UPSTREAM_BLOCKED
    )


def test_baidu_security_verify_is_upstream_blocked():
    assert classify_adapter_error({"error": "百度安全验证 网络不给力，请稍后重试"}) == ERR_UPSTREAM_BLOCKED
    assert classify_adapter_error({"error": "wappass 安全验证"}) == ERR_UPSTREAM_BLOCKED


def test_rate_limit_and_blocked_is_upstream_blocked():
    assert classify_adapter_error({"error": "rate limit exceeded"}) == ERR_UPSTREAM_BLOCKED
    assert classify_adapter_error({"error": "blocked by upstream"}) == ERR_UPSTREAM_BLOCKED
    assert classify_adapter_error({"error": "captcha required"}) == ERR_UPSTREAM_BLOCKED


def test_invalid_manifest_classified():
    assert classify_adapter_error({"error": "invalid manifest 格式错误"}) == ERR_INVALID_MANIFEST
    assert classify_adapter_error({"error": "无效规则"}) == ERR_INVALID_MANIFEST


def test_unknown_fallback():
    assert classify_adapter_error({"error": "some totally weird thing"}) == ERR_UNKNOWN_ERROR
    assert classify_adapter_error("") == ERR_UNKNOWN_ERROR
