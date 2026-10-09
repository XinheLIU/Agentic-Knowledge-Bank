# AI 知识库 · 项目愿景 v0.3

> Last updated: 2026-10-08
> v0.2 的旧版（采集/入库运行时）已被取代。本版按 [wiki-repositioning 计划](docs/exec-plans/wiki-repositioning.md)重写：本仓重新定位为「可追溯的概念 wiki」。模型冻结在 [docs/knowledge-model.md](docs/knowledge-model.md)。

## 要做什么

- 从一个外部的、只读的 **archive**（你积累的原始材料）出发，构建一个领域**知识实例**。
- 用三阶段把材料变成 wiki：`archive → materials.md（阶段 0 清单）→ notes/（阶段 1 证据）→ wiki/（阶段 2 呈现）`。
- 每个概念页按 L1–L4 深度模板撰写；**每一段都带 provenance id**，追溯到一行材料（`mat:`）或一个经验证的一手来源（`ext:`）。
- 在每次运行的关键节点设 **gate**：叙事与核心概念清单先与你确认，再写任何页面。
- 用一个只读的 lint 守护质量：层级覆盖矩阵、未解析脚注、archive sha 漂移、叙事与页面一致性。

## 两个目标

1. **认知资产积累** —— 一个从原始材料构建的 wiki，每条主张都可追溯、可学习、可按需深挖。
2. **认知复合** —— 推迟到后续设计，当前只保留草案材料。

## 不做什么

- 不做来源发现、采集编排与简报（Information Assistant 负责）。
- 不做 attempts / mastery 等学习状态（Learning OS 负责，本仓永不写入）。
- 不做写作与内容产出（Writing Assistant 负责，它把 wiki 页面与 `materials.md` 当作素材）。
- 不把内容写入 archive：archive 是只读的。
- 不发明内容：没有经验证来源就标 `gap`，绝不填补。
- 不引入语义/向量检索等重型依赖。

## 边界 & 验收

- **只读 archive**：任何技能都不写入 archive（不改名、不刷新 hash、不整理）。
- **逐段可追溯**：100% 脚注可解析，每个 `ext:` id 都有经验证的 URL 与版本。
- **清单可信**：`materials.md` 的 sha256 与 archive 中的文件一致。
- **深度诚实**：每个页面四个层级要么有内容、要么显式标 `gap`；覆盖矩阵是重点，不是失败。
- **叙事成立**：核心概念数量在 gate 上获得确认；与既有基线对照，主线叙事依然成立。

## 怎么验证

在真实数据上跑完一轮（Transformer 实例）：清单 → MECE 笔记 → 概念页 → lint。验收证据来自结构检查与你的 gate 确认，而不是条目数量；运行时行为在重构后尚未重新验证。
