# Phase 4E 安全与配置检查报告

生成时间：2026-08-19 15:32

## 结论先行

- 代码与脚本中**无明文凭据**（`_phase2_gray_run.py` 已改读环境变量）。
- 发现 **1 个未跟踪的备份文件** `.env.bak_20260806_152704` 含明文凭据（SECRET_KEY / INIT_ADMIN_PASSWORD / BAZHU_PASSWORD），**需人工轮换**。
- 前端新建数据源默认 `schedule_enabled=false`（手动模式），符合要求。
- runtime lock / 路径 / 端口 / 目录配置与真实运行实例一致（见 Phase 4A）。

---

## 一、明文凭据扫描

| 检查项 | 结果 |
|--------|------|
| 代码/脚本明文密码/token | ✅ 无（正则扫描 backend/ + frontend/src/ 无匹配） |
| `_phase2_gray_run.py` | ✅ 已改读 `YQ_ADMIN_PASSWORD` 环境变量 |
| git 跟踪的 .env | ✅ 仅 `.env.example`（无真实凭据） |
| `.env.bak_20260806_152704`（未跟踪） | ⚠️ **含明文凭据**（见下） |
| daemon.json / token / cookie 文件进 git | ✅ 无 |
| 项目内 daemon.json | ✅ 不在项目目录（位于 `~/.bb-browser/`，运行时凭据） |

## 二、发现的明文凭据（需人工轮换）

文件：`.env.bak_20260806_152704`（未跟踪，2026-08-06 的 .env 备份）

| 键 | 风险 | 处理 |
|----|------|------|
| `SECRET_KEY` | 应用签名密钥，泄露可伪造会话 | 人工轮换 |
| `INIT_ADMIN_PASSWORD` | 管理员初始口令 | **立即轮换** |
| `BAZHU_PASSWORD` | 八爪鱼 API 口令 | 人工轮换 |

**agent 不自行判定"已处理"**，仅标记需人工轮换。此文件不会进入 git（未跟踪），但建议由用户决定是否移动/删除。

## 三、前端 schedule_enabled 默认值

| 位置 | 默认值 | 判定 |
|------|--------|------|
| 新建数据源 form（Sources.vue:799） | `schedule_enabled: false` | ✅ 手动模式 |
| bb-browser 提示（Sources.vue:431） | "默认手动，灰度期间必须保持手动" | ✅ 明确 |
| 单源调度弹窗 draft（:743） | `true` | ⚠️ 打开时被 `!!row.schedule_enabled` 覆盖，非误导 |
| 批量调度弹窗（:750） | `true` | 观察项：批量"统一采集频率"默认开启，属用户主动操作，未改 |

**结论**：新建源默认手动，满足"默认必须是手动模式"。批量弹窗默认 true 属批量操作的合理 UX，未做改动（避免过度设计）。

## 四、配置一致性

- runtime lock：worker/CLI SHA256 匹配、bb-sites HEAD 匹配（Phase 4A 已验证）。
- CDP 9222 / daemon 19824 / profile / exchange_root / control_root 与 lock 一致。
- source 62：`schedule_enabled=false`，config_json 五平台 + allow_weibo=false + allow_xiaohongshu=false。

## 五、结论

1. 代码无明文凭据；`_phase2_gray_run.py` 已环境变量化。
2. `.env.bak_20260806_152704` 含明文凭据，**需人工轮换**（尤其 INIT_ADMIN_PASSWORD），agent 未自行处理。
3. 前端默认手动模式，符合要求。
4. 配置与运行实例一致。
