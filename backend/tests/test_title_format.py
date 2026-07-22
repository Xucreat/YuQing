"""title_format 共享规则单元测试（纯函数，无 DB 依赖，快速回归）。

锁定『一条具体标题 + 等N条相关舆情聚集』这一聚合与回填共用的标题规则：
  - 基础形式
  - 过长时省略号截断
  - 无代表标题时降级为『共N条相关舆情聚集』
  - representative_title 取最早（入参顺序首个）非空标题
"""
from app.services.event.title_format import (
    TITLE_SOFT_MAX,
    build_cluster_title,
    representative_title,
)


class _Fake:
    def __init__(self, title):
        self.title = title


def test_basic_cluster_title():
    t = build_cluster_title("河北多举措推进基础教育扩优提质", 2)
    assert t == "河北多举措推进基础教育扩优提质等2条相关舆情聚集"
    assert "（" not in t and "）" not in t  # 不再使用旧「（risk风险）」形式


def test_cluster_title_with_single_member_count():
    t = build_cluster_title("某舆情标题", 1)
    assert t == "某舆情标题等1条相关舆情聚集"


def test_cluster_title_truncation_with_ellipsis():
    # 代表标题足够长，组合后超过 TITLE_SOFT_MAX(80)，应触发省略号截断
    long_rep = "河" * 100
    t = build_cluster_title(long_rep, 2)
    assert "…" in t
    assert t.endswith("等2条相关舆情聚集")
    assert len(t) <= TITLE_SOFT_MAX
    # 省略号前的具体内容被截断
    assert long_rep not in t


def test_cluster_title_empty_representative_fallback():
    t = build_cluster_title("", 3)
    assert t == "共3条相关舆情聚集"
    assert "（" not in t


def test_representative_title_picks_earliest_nonempty():
    members = [_Fake(""), _Fake("第二条"), _Fake("第三条")]
    assert representative_title(members) == "第二条"


def test_representative_title_all_empty():
    assert representative_title([_Fake(""), _Fake("  ")]) == ""


def test_soft_max_boundary_no_false_truncation():
    # 恰好等于软上限的组合不应被截断（无省略号）
    rep = "河北"  # 2 字
    suffix = "等5条相关舆情聚集"  # 9 字
    # 构造一个总长度恰好 <= TITLE_SOFT_MAX 的代表标题
    rep_exact = "河" * (TITLE_SOFT_MAX - len(suffix))
    t = build_cluster_title(rep_exact, 5)
    assert "…" not in t
    assert len(t) <= TITLE_SOFT_MAX
    # 仅超出 1 字即触发省略号
    t2 = build_cluster_title(rep_exact + "北", 5)
    assert "…" in t2
