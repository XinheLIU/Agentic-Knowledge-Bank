# Hooks 规格

> Last updated: 2026-05-02

## hooks/validate_json.py

校验知识条目 JSON 文件。

需求：
1. 支持单文件和多文件（通配符 `*.json`）两种输入模式
2. 检查 JSON 是否能正确解析
3. 必填字段使用 `dict[str, type]` 格式，同时校验字段存在性和类型：
   `id`(str), `title`(str), `source_url`(str), `summary`(str), `tags`(list), `status`(str)
4. 检查 ID 格式：现有条目使用 `{owner}/{repo}` 格式（如 `99xAgency/GodModeSkill`），
   也兼容 `{source}-{YYYYMMDD}-{NNN}` 格式（如 `github-20260317-001`）
5. 检查 `status` 是否为 `draft` / `review` / `published` / `archived` 之一
6. 检查 URL 格式（`https?://...`）
7. 检查摘要最少 20 字、标签至少 1 个
8. 检查 `score`（如有）是否在 1-10 范围，`audience`（如有）是否为 `beginner` / `intermediate` / `advanced`
9. 命令行用法：`python hooks/validate_json.py <json_file> [json_file2 ...]`
10. 校验通过 exit 0，失败 exit 1 + 错误列表 + 汇总统计

编码规范：遵循 PEP 8，使用 pathlib，不依赖第三方库

---

## hooks/check_quality.py

给知识条目做 5 维度质量评价。

需求：
1. 支持单文件和多文件（通配符 `*.json`）两种输入模式
2. 使用 dataclass 定义 `DimensionScore` 和 `QualityReport` 结构
3. 5 个评分维度及满分（加权总分 100 分）：
   - 摘要质量 (25 分)：>= 50 字满分，>= 20 字基本分，含技术关键词有奖励
   - 技术深度 (25 分)：基于文章 `score` 字段（1-10 映射到 0-25）
   - 格式规范 (20 分)：`id`、`title`、`source_url`、`status`、时间戳五项各 4 分
   - 标签精度 (15 分)：1-3 个合法标签最佳，有标准标签列表校验
   - 空洞词检测 (15 分)：不含空洞词满分，每出现一个扣 3 分
4. 空洞词黑名单分中英两组：
   - 中文：赋能、抓手、闭环、打通、全链路、底层逻辑、颗粒度、对齐、拉通、沉淀、强大的、革命性的
   - 英文：groundbreaking、revolutionary、game-changing、cutting-edge、state-of-the-art、leverage、synergy、paradigm shift、disruptive、next-generation、world-class
5. 输出可视化进度条 + 每维度得分 + 等级 A/B/C
6. 等级标准：A >= 80, B >= 60, C < 60
7. 退出码：存在 C 级返回 1，否则返回 0

编码规范：遵循 PEP 8，使用 pathlib 和 dataclass，不依赖第三方库