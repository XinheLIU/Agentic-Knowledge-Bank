---
name: metrics-tracker
description: >
  记录 pipeline 各阶段运行指标，支持结构化日志和汇总报告。
  各 Agent 在运行前后调用本技能记录关键数据。
---

# Metrics Tracker 技能

## 职责
- 记录每阶段运行时间、处理数、成功/失败数
- 输出结构化日志到 `logs/` 目录
- 生成运行摘要供用户审阅

## 日志格式（JSON Lines）

```json
{
  "timestamp": "2026-04-29T08:00:00Z",
  "stage": "collector",
  "source": "github-trending",
  "total": 125,
  "success": 125,
  "failed": 0,
  "duration_ms": 4500
}
```

## 输出文件
- `logs/pipeline-{YYYY-MM-DD}.jsonl` — 每条运行记录
- `logs/summary-{YYYY-MM-DD}.log` — 人类可读摘要

## 摘要模板

```
[2026-04-29 08:00:00] Pipeline 运行摘要
==================================================
[Collector]  3 sources | 125 total | 0 failed | 4.5s
[Analyzer]   20 items | 18 success | 2 failed | 12.3s
[Organizer]  18 items | 15 written | 3 filtered (score<0.6)
--------------------------------------------------
产出：knowledge/articles/2026-04-29-*.md (15 files)
索引：knowledge/articles/index.json
```

## 指标定义

| 指标 | 含义 | 记录方 |
|---|---|---|
| `total` | 本阶段处理的条目总数 | 各 Agent |
| `success` | 成功处理的条目数 | 各 Agent |
| `failed` | 失败/跳过的条目数 | 各 Agent |
| `filtered` | 被质量门控过滤的条目数 | Organizer |
| `duration_ms` | 本阶段耗时（毫秒） | 各 Agent |
| `relevance_avg` | 平均 relevance_score | Analyzer |

## 规则
- 所有日志输出通过标准 `logging` 模块，禁止裸 `print()`
- 日志按日期切分，不提交 git
- 错误明细写入 `knowledge/raw/errors-{date}.json`
