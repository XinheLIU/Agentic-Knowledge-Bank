# 知识库 / Agentic Knowledge Bank

Last updated: 2026-10-09

本仓构建**可追溯的概念 wiki**。一个*知识实例*是最终产物：一个主题的完整理解，由叙事组织、在每个概念内部足够深入可供学习，并且每一段都逐段追溯到它的原始材料或权威一手来源。

领域模型冻结在 [docs/knowledge-model.md](docs/knowledge-model.md)，术语表见 [CONTEXT.md](CONTEXT.md)。

## 两个目标

1. **认知资产积累** —— 一个从原始材料构建的 wiki，其中每一条主张都追溯到一行材料或一个权威一手来源。
2. **认知复合** —— 推迟到后续设计，当前只保留草案材料。

## 流水线

```
archive          ──map-materials──▶  materials.md  ──clean-notes──▶  notes/  ──llm-wiki-ingest──▶  wiki/
(只读)                               阶段 0：清单                   阶段 1：证据                  阶段 2：呈现
```

每个阶段职责不同，且不可跳过：

- **清单**（`map-materials`）—— 每份材料一行：路径、种类、角色、sha256、概念、标记。archive 是外部事实来源，清单写入实例。
- **笔记**（`clean-notes`）—— 一个主题的材料经过合并、去重与聚类，provenance id 原样保留。笔记是*证据*：不添加、不改进、不评判。
- **Wiki**（`llm-wiki-ingest`）—— 按 L1–L4 深度模板撰写的概念页，每一段都带脚注。`llm-wiki-lint` 审计层级覆盖、未解析脚注、sha 漂移与一致性。

**archive** 是你积累的外部文件夹，以绝对路径引用，**永不写入**。`materials.md`、`notes/` 与 `wiki/` 位于实例内；实例数据在本仓之外，绝不打包。

## 关系

| 产品 | 与本仓的关系 |
|---|---|
| **Information Assistant** | 上游。负责来源发现，拥有跨主题来源注册表与信任轴。其产出可以成为本仓的原始输入。 |
| **Learning OS** | 下游。把 wiki 页面作为学习材料读取，拥有 attempts 与 mastery。本仓永不写入。 |
| **Writing Assistant** | 下游。把 wiki 页面与 `materials.md` 作为有出处的素材使用，拥有 `archive-materials` 与 `used-in` 列。 |
| **Synapse** | 对已发布 wiki 页面的派生跨来源索引。 |

## 入口

- [架构与边界](docs/architecture.md)
- [知识模型](docs/knowledge-model.md)
- [领域不变量](docs/domain-invariants.md)
- [重定位计划](docs/exec-plans/wiki-repositioning.md)
- [Agent 指令](AGENTS.md)
- [技能目录](catalog/skill-set.json)

## 状态

知识模型已冻结，四个技能已按其重写。[计划](docs/exec-plans/wiki-repositioning.md) Phase C 的 Transformer 运行已**通过**（2026-10-09）：每个脚注可解析、每个 `ext:` id 都有经验证的 URL、每个 `materials.md` 行的 sha256 都与 archive 一致。Phase A–C 已完成，Phase D（技能安装/导出与发布）仍待完成。不要用结构性检查推断运行时行为。
