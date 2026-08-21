# 舆情监测系统 v1.0.0 归档清单（MANIFEST）

> 冻结提交（main 顶端）：`8fdf516f`（含 `1d9556bc` 测试修复）
> 标签：`v1.0.0-final`（annotated，已创建并推送）
> 生成日期：2026-08-21（Asia/Shanghai）

## 1. 仓库归档（git bundle）

| 项 | 值 |
|---|---|
| 路径 | `runtime/v1.0.0-final/yq-v1.0.0-final.bundle` |
| 大小 | 672,011,926 字节（约 641 MiB，含完整历史） |
| SHA-256（含 v1.0.0-final 标签的最终归档） | `7209A62143BF0DEA415E8B459D72DADDA84AB4567281838D0FE8824D83274F95` |
| 命令 | `git bundle create runtime/v1.0.0-final/yq-v1.0.0-final.bundle --all` |
| 校验 | `git bundle verify` 通过（“records a complete history”） |

> 说明：bundle 已包含 `v1.0.0-final` 标签与冻结提交 `8fdf516f`，上述 SHA-256 为最终分发版本。

## 2. 数据库只读备份（pg_dump）

| 项 | 值 |
|---|---|
| 路径 | `runtime/v1.0.0-final/opinion_db_20260821_140727.dump` |
| 格式 | custom（`-Fc`） |
| 大小 | 2,415,529 字节 |
| SHA-256 | `8D3442B692F2CEF68C0C4543B2CABE83F02D31DA60D307910BF91C0AE2E1A7CA` |
| 命令 | `pg_dump -Fc -h 127.0.0.1 -p 5432 -U opinion_user -d opinion_db -f <path>`（只读，未修改生产库） |

- 全局对象建议另存：`pg_dumpall --globals-only --no-role-passwords`（本阶段未强制生成）。
- 恢复须在**隔离** PostgreSQL 实例进行，禁止覆盖生产库。

## 3. 交付文档（10 份，入库）

| # | 文件（相对仓库根） |
|---|---|
| 1 | `docs/release/v1.0.0-final/系统白皮书_交付稿.md` |
| 2 | `docs/release/v1.0.0-final/数据库冻结报告.md` |
| 3 | `docs/release/v1.0.0-final/安全审计交付报告.md` |
| 4 | `docs/release/v1.0.0-final/RBAC收口交付报告.md` |
| 5 | `docs/release/v1.0.0-final/测试与流水线报告.md` |
| 6 | `docs/release/v1.0.0-final/部署与运维手册.md` |
| 7 | `docs/release/v1.0.0-final/遗留问题清单.md` |
| 8 | `docs/release/v1.0.0-final/RELEASE_NOTES.md` |
| 9 | `docs/release/v1.0.0-final/MANIFEST.md`（本文件） |
| 10 | `docs/release/v1.0.0-final/验收报告.md` |

## 4. 代码变更（本冻结相对上一阶段）

- `backend/tests/test_rbac_hardening.py`：修复 pytest collection 导入期连接测试库挂起（测试基础设施-only：生产库守卫 + `connect_timeout=5`）。
- `.gitignore`：追加 `/tmp/`，防止浏览器凭据缓存误入库。

## 5. 明确不入库项（gitignored）

- `.env` / `.env.local`（含数据库与 API 凭据；仅 `.env.example` 入库）
- `tmp/`（浏览器凭据缓存，含 `Login Data`/`Cookies`/`Local State`/`trusted_vault.pb`；物理文件须人工清理与凭据轮换）
- `node_modules/`、`frontend/dist/`、`backend/.venv/`、`__pycache__/`、`.pytest_cache/`
- `runtime/`（本归档产物目录自身）

## 6. 安全扫描结论

- 跟踪文件中未发现 `.env` 或明文口令（见《安全审计交付报告》与验收报告）。
- 唯一残留风险为工作区 `tmp/` 物理凭据缓存（已忽略未跟踪，待归档分发前清理）。

## 7. 校验步骤

```powershell
# 校验 bundle 完整性与可克隆
git bundle verify runtime/v1.0.0-final/yq-v1.0.0-final.bundle
git clone -b main runtime/v1.0.0-final/yq-v1.0.0-final.bundle yq-verify

# 校验 dump 完整性与可恢复（隔离实例）
pg_restore --list runtime/v1.0.0-final/opinion_db_20260821_140727.dump | Select-Object -First 5
```
