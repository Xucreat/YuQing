"""Phase 5 阶段四：百度退避/冷却计算纯函数测试。"""
from app.collectors.bb_browser_runtime import compute_backoff_delay, in_cooldown


def test_backoff_base_for_first_attempt():
    assert compute_backoff_delay(0, base_seconds=60) == 60
    assert compute_backoff_delay(1, base_seconds=60) == 60


def test_backoff_exponential_growth():
    assert compute_backoff_delay(2, base_seconds=60) == 120
    assert compute_backoff_delay(3, base_seconds=60) == 240
    assert compute_backoff_delay(4, base_seconds=60) == 480


def test_backoff_capped_at_max():
    assert compute_backoff_delay(10, base_seconds=60, max_seconds=3600) == 3600


def test_backoff_conservative_defaults():
    # 默认 base=60 max=3600
    assert compute_backoff_delay(1) == 60
    assert compute_backoff_delay(2) == 120


def test_in_cooldown_true_within_window():
    assert in_cooldown(blocked_at_ts=1000.0, now_ts=1100.0, cooldown_seconds=600) is True


def test_in_cooldown_false_after_window():
    assert in_cooldown(blocked_at_ts=1000.0, now_ts=1600.0, cooldown_seconds=600) is False


def test_in_cooldown_invalid_inputs():
    assert in_cooldown(blocked_at_ts=0, now_ts=100.0, cooldown_seconds=600) is False
    assert in_cooldown(blocked_at_ts=100.0, now_ts=200.0, cooldown_seconds=0) is False
