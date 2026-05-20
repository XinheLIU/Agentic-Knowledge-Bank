## ADDED Requirements

### Requirement: category 必须是单值
Analyzer 输出 `category` SHALL 是 `{llm, agent, rag, mcp, evaluation, deployment, security, other}` 中的单个字符串，不允许包含 `|` 或数组。

#### Scenario: 合法单值通过
- **WHEN** analyzer 返回 `category: "agent"`
- **THEN** organizer SHALL 接受并写入

#### Scenario: 多值字符串被拒绝并降级
- **WHEN** analyzer 返回 `category: "agent|evaluation"`
- **THEN** organizer SHALL 拒绝、取第一段作为 `category`、剩余值追加到 `tags`、并把条目 `status` 置为 `review`

### Requirement: analyzer prompt 明确单值约束
`workflows/analyzer.py` 的 prompt SHALL 显式列出枚举值数组并要求"从下列单一值中选一个"，且 SHALL 包含一个反例说明"不要返回 `a|b` 这种多值字符串"。

#### Scenario: prompt 文本包含约束句
- **WHEN** 读 `analyzer.py` 的 prompt 字符串
- **THEN** 文本 SHALL 同时出现 "select one" 类指令与反例标记

### Requirement: relevance_score 写全量
Analyzer SHALL 把模型给出的 `relevance_score` 原值（包含 < 阈值的样本）写入 JSON。阈值过滤 SHALL NOT 在写入前发生。

#### Scenario: 低分条目不再被静默丢弃
- **WHEN** analyzer 对某条返回 `relevance_score = 0.42`
- **THEN** 该分数 SHALL 出现在最终 JSON 或 `_skipped.jsonl` 中（取决于是否被淘汰），而非被丢失

### Requirement: audience 通过 few-shot 提示判断
Analyzer prompt SHALL 包含至少 3 个 few-shot 示例（beginner / intermediate / advanced 各一），并要求模型先输出判断理由再给出 `audience` 值。

#### Scenario: prompt 含 few-shot 示例
- **WHEN** 读 `analyzer.py` 的 prompt
- **THEN** 文本 SHALL 至少出现 3 个 audience 取值各一次的示例段
