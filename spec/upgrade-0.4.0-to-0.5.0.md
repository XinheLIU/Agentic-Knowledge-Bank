# AI 知识库 0.4.0 -> 0.5.0 升级说明
> Last updated: 2026-05-06

## 背景

`0.4.0` 使用线性 `pipeline/`：采集、分析、整理、保存串行执行。这个结构简单，但状态与分支逻辑是隐式的，无法自然表达“审核失败后修订再审”以及“多次失败后人工介入”。

`0.5.0` 将主流程迁移到 LangGraph，用显式图结构表达节点、状态与条件路由。

## 为什么改成 LangGraph

### 优点
- 显式状态：`plan`, `sources`, `analyses`, `iteration`, `review_feedback` 等字段集中定义
- 条件路由清晰：`review -> organize | revise | human_flag`
- 更适合闭环：审核、修订、再审核是图结构，不是脚本里堆条件分支
- 更容易测试：节点函数可单测，路由函数可独立验证
- 更容易扩展：以后加 `search`, `rank`, `multi-source planner`, `human approval` 不需要推倒入口

### 代价
- 引入 `langgraph` 依赖，概念复杂度高于线性脚本
- 需要维护状态契约，否则节点之间容易失配
- 测试面更广：不仅要测函数，还要测路由和终点行为

## 新设计

```text
plan -> collect -> analyze -> review
                             | pass -> organize -> END
                             | fail & iteration < max -> revise -> review
                             | fail & iteration >= max -> human_flag -> END
```

### 节点职责
- `Planner`：根据目标采集量输出策略
- `Collector`：执行 GitHub + RSS 采集
- `Analyzer`：逐条 LLM 分析
- `Reviewer`：五维加权审核，总分由代码重算
- `Reviser`：根据反馈定向修改分析结果
- `Organizer`：过滤、去重、格式化、入库
- `HumanFlag`：将失败批次写入 `knowledge/pending_review/`

## 与 0.4.0 的差异

### 删除
- `pipeline/`
- `scripts/`
- 旧的兼容入口

### 保留
- GitHub + RSS 采集能力
- OpenAI-compatible HTTP 模型客户端方向
- hooks 校验与 MCP 服务

### 新增
- `workflows/graph.py`
- `workflows/state.py`
- `knowledge/pending_review/`
- notebook 演示

## 自动化语义变化

- GitHub Actions 现在执行 `python -m workflows.graph`
- 定时任务带 `--fail-on-human-flag`，因此 `HumanFlag` 不再算“成功但待处理”，而是直接标记本次自动采集失败
- 定时任务只提交 `knowledge/articles/` 与 `knowledge/raw/`，不提交 `knowledge/pending_review/`

## 迁移结论

如果目标只是“一次采集，一次分析，然后落盘”，线性脚本更轻。

如果目标是“多节点协作、显式状态、审核闭环、未来可扩展”，LangGraph 更合适。当前项目已经进入第二种阶段，因此 `0.5.0` 的迁移是合理的。
