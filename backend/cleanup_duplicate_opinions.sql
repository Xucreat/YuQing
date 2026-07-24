-- ============================================================================
-- 清理方案：重复舆情 + 重复事件关联（仅供人工复核后执行，本任务不自动执行）
-- ----------------------------------------------------------------------------
-- 目的：为应用迁移 p6urluniq01 (opinions.url 部分唯一索引) 与
--       p7evtuniq01 (event_opinions 关联唯一约束) 扫清障碍（两约束创建前
--       库内不能存在重复，否则迁移会失败）。
-- 原则：每组精确 url 重复，保留最小 id（最早采集）那条，删除其余冗余；
--       删除前先将 delete 舆情的 event_opinions 转移到 keep（避免事件关联
--       丢失，且不产生重复关联）；绝对不丢弃业务语义。
-- 安全加固（依据生产落地前安全审计结论，2026-07-24）：
--   • 自引用外键：待删舆情节点可能被“保留节点”作为 parent_id 引用。删除待删
--     节点前先将这些 parent_id 置 NULL，避免触发 NO ACTION 冲突导致整事务回滚。
--   • 全程单事务；任一步失败可整体 ROLLBACK。
-- ⚠ 执行前务必对 opinion_db 做一次全量备份。
-- ⚠ 整个清理在一个事务内完成；执行后先核对验证查询（第 4 步），确认无误再
--   COMMIT，否则 ROLLBACK。
-- 关联影响（已只读核实）：33 条待删舆情共牵连 alert_records 5 行、
--       propagation_nodes 59 行（含 5 个跨舆情父引用，已用 0.6 置空处理）、
--       event_opinions 61 行（已在 0.5 转移给 keep，删除时其行已为 0，
--       第 1/2 步的删除为安全兜底）。
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 0) 只读预览（先核对影响范围；本段在事务内执行也安全，仅 SELECT）
-- ---------------------------------------------------------------------------
SELECT
  (SELECT count(*) FROM (
     SELECT o.id FROM opinions o
     JOIN (SELECT url, min(id) keep_id FROM opinions WHERE url<>'' GROUP BY url HAVING count(*)>1) d
       ON d.url=o.url WHERE o.id<>d.keep_id) t) AS opinions_to_delete;

SELECT
  (SELECT count(*) FROM alert_records ar
     WHERE ar.opinion_id IN (
       SELECT o.id FROM opinions o
       JOIN (SELECT url, min(id) keep_id FROM opinions WHERE url<>'' GROUP BY url HAVING count(*)>1) d
         ON d.url=o.url WHERE o.id<>d.keep_id)) AS alert_records_to_delete,
  (SELECT count(*) FROM propagation_nodes pn
     WHERE pn.opinion_id IN (
       SELECT o.id FROM opinions o
       JOIN (SELECT url, min(id) keep_id FROM opinions WHERE url<>'' GROUP BY url HAVING count(*)>1) d
         ON d.url=o.url WHERE o.id<>d.keep_id)) AS propagation_nodes_to_delete,
  (SELECT count(*) FROM event_opinions eo
     WHERE eo.opinion_id IN (
       SELECT o.id FROM opinions o
       JOIN (SELECT url, min(id) keep_id FROM opinions WHERE url<>'' GROUP BY url HAVING count(*)>1) d
         ON d.url=o.url WHERE o.id<>d.keep_id)) AS event_opinions_for_dup_opinions_to_delete,
  (SELECT count(*) FROM (
       SELECT event_id, opinion_id, min(id) keep_id FROM event_opinions
       GROUP BY event_id, opinion_id HAVING count(*)>1) t) AS event_opinion_dups_to_delete;

-- ---------------------------------------------------------------------------
-- 0.5) 将 delete opinion 的 event_opinions 转移到 keep opinion
--      （在删除之前迁移，避免事件关联丢失；NOT EXISTS 保证不产生重复关联）
-- ---------------------------------------------------------------------------
INSERT INTO event_opinions (event_id, opinion_id)
SELECT eo.event_id, d.keep_id
FROM event_opinions eo
JOIN (
  SELECT url, min(id) keep_id
  FROM opinions WHERE url <> ''
  GROUP BY url HAVING count(*) > 1
) d ON d.url = (SELECT o.url FROM opinions o WHERE o.id = eo.opinion_id)
WHERE eo.opinion_id <> d.keep_id
  AND NOT EXISTS (
    SELECT 1 FROM event_opinions x
    WHERE x.event_id = eo.event_id AND x.opinion_id = d.keep_id
  );

-- ---------------------------------------------------------------------------
-- 1) 删除「待删舆情」在 alert_records / propagation_nodes / event_opinions 的关联
--    （避免外键 NO ACTION 冲突；顺序：先子表，后主表）
--    event_opinions 中 delete 舆情的部分已在 0.5 转移给 keep，此处为安全兜底
-- ---------------------------------------------------------------------------
DELETE FROM alert_records
WHERE opinion_id IN (
  SELECT o.id FROM opinions o
  JOIN (SELECT url, min(id) keep_id FROM opinions WHERE url<>'' GROUP BY url HAVING count(*)>1) d
    ON d.url=o.url WHERE o.id<>d.keep_id
);

-- ---------------------------------------------------------------------------
-- 0.6) 断开 propagation_nodes 自引用（最小安全方案）：
--      待删舆情节点可能被“保留节点”作为 parent_id 引用（跨舆情传播链）。
--      删除待删节点前，先将这些 parent_id 置 NULL，避免触发 NO ACTION 冲突
--      导致整事务回滚。事务内执行，任一步失败可整体 ROLLBACK。
-- ---------------------------------------------------------------------------
UPDATE propagation_nodes
SET parent_id = NULL
WHERE parent_id IN (
  SELECT id FROM propagation_nodes
  WHERE opinion_id IN (
    SELECT o.id FROM opinions o
    JOIN (SELECT url, min(id) keep_id FROM opinions WHERE url<>'' GROUP BY url HAVING count(*)>1) d
      ON d.url=o.url WHERE o.id<>d.keep_id
  )
);

DELETE FROM propagation_nodes
WHERE opinion_id IN (
  SELECT o.id FROM opinions o
  JOIN (SELECT url, min(id) keep_id FROM opinions WHERE url<>'' GROUP BY url HAVING count(*)>1) d
    ON d.url=o.url WHERE o.id<>d.keep_id
);

DELETE FROM event_opinions
WHERE opinion_id IN (
  SELECT o.id FROM opinions o
  JOIN (SELECT url, min(id) keep_id FROM opinions WHERE url<>'' GROUP BY url HAVING count(*)>1) d
    ON d.url=o.url WHERE o.id<>d.keep_id
);

-- ---------------------------------------------------------------------------
-- 2) 删除 event_opinions 中剩余的 (event_id, opinion_id) 字面重复行（保留最小 id）
-- ---------------------------------------------------------------------------
DELETE FROM event_opinions
WHERE id IN (
  SELECT eo.id FROM event_opinions eo
  JOIN (SELECT event_id, opinion_id, min(id) keep_id FROM event_opinions
        GROUP BY event_id, opinion_id HAVING count(*)>1) d
    ON d.event_id=eo.event_id AND d.opinion_id=eo.opinion_id
  WHERE eo.id<>d.keep_id
);

-- ---------------------------------------------------------------------------
-- 3) 删除冗余舆情（每组保留最小 id）
-- ---------------------------------------------------------------------------
DELETE FROM opinions
WHERE id IN (
  SELECT o.id FROM opinions o
  JOIN (SELECT url, min(id) keep_id FROM opinions WHERE url<>'' GROUP BY url HAVING count(*)>1) d
    ON d.url=o.url WHERE o.id<>d.keep_id
);

-- ---------------------------------------------------------------------------
-- 4) 执行后验证：以下查询应均返回 0；确认无误再 COMMIT，否则 ROLLBACK
-- ---------------------------------------------------------------------------
SELECT 'exact_url_dups' AS chk, count(*) AS n FROM (
  SELECT url FROM opinions WHERE url<>'' GROUP BY url HAVING count(*)>1) t
UNION ALL
SELECT 'event_opinion_dups', count(*) FROM (
  SELECT event_id, opinion_id FROM event_opinions GROUP BY event_id, opinion_id HAVING count(*)>1) t;

-- 若上一步两项均为 0，且业务核查无误，则：
--   COMMIT;
-- 否则：
--   ROLLBACK;
--
-- 提交后，再执行迁移（会先经数据库身份门禁校验为生产库）：
--   alembic upgrade head        -- 应用 p6urluniq01 + p7evtuniq01
-- ============================================================================
