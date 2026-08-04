"""National-mode 常量（National-Mode-2 数据准备引入）。

设计：全国身份由固定 ``Region.code`` 表达，**不新增任何数据库字段 / 不新增
``national`` / ``is_national`` 列**。National-Mode-2 负责插入一条
``code='000000' name='全国'`` 的哨兵 Region 数据行；后续 National-Mode-4 准入逻辑
复用本常量作为「全国兜底 region_id」的唯一来源，避免字符串散落复制。
"""
from __future__ import annotations

# 系统级「全国」哨兵 Region 的行政区划 code。
# 选择 "000000" 的依据（详见 Phase DataSource-National-Mode-2 PreAudit）：
#   - 长度 6 位，与现有 GB/T 2260 体系（省 130000 / 市 131000 / 县 131028）格式兼容；
#   - 全零哨兵语义清晰（"全国" = 未限定具体行政区）；
#   - dashboard `_province_code("000000")` 推导 key="000000"，
#     与任何真实省前缀（13/44/…）不冲突，独立成键、不会错误上卷。
NATIONAL_REGION_CODE = "000000"
