# 知识库爬取 / 筛选 / 加工 / 验证策略评审

> Last updated: 2026-05-13
> 目的：检视现行 collector → analyzer → reviewer → organizer 链路的策略问题，给出可执行的更新建议
> 配套：与 [knowledge-content-review.md](knowledge-content-review.md)（数据现状审计）共同食用

---

## 0. 总览

现行链路：

```
planner ─► collector ─► analyzer ─► reviewer ─► organizer
   │           │           │           │           │
 选档位       拉取        每条LLM     抽样5条      去重写盘
                          摘要/打分    LLM审核
```

**核心判断**：这是一条"啥都让 LLM 干"的链路。便宜的硬过滤几乎没有，规则可解决的判断被花钱让模型再判断一次，而真正需要 LLM 判断的部分（语义去重、跨条对比、价值排序）反而没做。

---

## 1. Collector 层：硬伤先于策略

### 1.1 RSS limit 全局共享 ≠ 每源 limit
```python
# collector.py:75-122
for source in sources:
    if len(items) >= limit: break       # ← 整批 limit
    for entry in feed.entries:
        if len(items) >= limit: break   # ← 同一个 limit
```
配置文件名叫 `per_source_limit`、planner 的字段也叫 `per_source_limit`，但实际是**整个 RSS 的总 limit**。后果：YAML 里前几个源就把名额吃光（Hacker News + Reddit r/ML 在前，后面 arXiv/OpenAI/Anthropic 永远 0 条）。

→ 这正好解释了为什么 95/140 来自 r/ML，arXiv 和厂商博客几乎拿不到。

**修复**：单源独立 limit，外层用 `aggregate_limit` 控总量。

```python
for source in sources:
    source_items = []
    for entry in feed.entries:
        if len(source_items) >= per_source_limit: break
        source_items.append(...)
    items.extend(source_items)
```

### 1.2 RSS 没用 `published_parsed`
feedparser 解析出来的 `entry.published_parsed` 才是真实发布时间，现在直接 `published_at = collected_at`，等于丢字段。

### 1.3 GitHub 单 query 撞星权重头
```python
"q": "ai agent llm stars:>100 pushed:>{week_ago}"
"sort": "stars"
```
按 stars 降序，每天前 N 永远是 dify/langchain/ragflow 这些头部仓库。**这就是为什么 GitHub 类别在 5 天内反复采到同一批仓库**（raw 文件里 langgenius/dify 出现了 N 次）。

→ 现在靠 organizer 的 URL 去重兜底，但相当于每天浪费 LLM 调用去分析昨天分析过的同一个 repo。

**修复路线（按成本排）**：
- 改 query：`created:>` 而非 `pushed:>`，过滤掉只是定期 commit 的老仓库
- 加 query 分桶：分多个 `language:python` / `topic:agents` / `topic:rag` 拉取，组合去重
- 在 collector 内对 `source_url` 跨日去重（用 `_existing_urls()` 复用，目前这个函数只在 organizer 用），**收集阶段就别拉重复条目**

### 1.4 Reddit hot.rss 噪声极高
`hot.rss` 是社区"当前热度"，**meta 帖（招聘、开会、政策、吐槽）混在研究帖里**。看 corpus，"What W&B's new MSA means"、"NeurIPS 2026 AC-Pilot 你信不信"、"Stop letting LLMs edit your .bib" 这类讨论占比很大，技术信息密度低。

**修复**：
- 改用 `top/week.rss` 或 `top/day.rss?t=day`，减少噪声
- 或加 `flair` 过滤（`[R]` 研究、`[P]` 项目、`[D]` 讨论）—— hot.rss 里 flair 就在 title 前缀，可以正则过滤掉非 `[R]/[P]`

### 1.5 OpenAI / Anthropic / Google AI / HF / LangChain Blog 实际产出为 0
配置 enabled=true，但成品里没看到这些源。两种可能：
- 这些 feed 在 1.1 的 limit 共享下永远排不上
- 这些 feed 本周确实没新内容

→ 建议 collector 打印每源拉取/接受条数，做最低 observability。

---

## 2. Analyzer 层：LLM 干了硬规则的活

### 2.1 每条都进 LLM，没有前置漏斗
现在 40 条 raw 全部进 LLM。便宜的预过滤完全缺失。

**应该在调 LLM 之前先做**（每条 < 1ms）：

| 过滤 | 规则 | 预期淘汰率 |
|---|---|---|
| URL 黑名单 | reddit meta（`/r/MachineLearning/wiki/`, `/comments/X/discussion_thread`）、招聘 | ~5% |
| 标题正则黑名单 | `\[D\]\s*meta`, `Job`, `Hiring`, `Survey`, `Announcement`, `Discussion thread` | ~10% |
| 标题/描述语言+长度 | title < 8 字 或 > 200 字、description 全是 `Article URL:` 模板 | ~15% |
| 同 URL 已入库 | 跨日去重 | 视情况 |
| GitHub 仓库已入库且 stars 增量 < 5% | 旧仓库无意义重采 | ~30% |

把这些先做掉，LLM 调用量直接砍掉一半以上。

### 2.2 RSS `raw_description` 其实是 HTML 模板
看 raw：
```
"raw_description": "<p>Article URL: <a href=\"...\">...</a></p>
                    <p>Comments URL: ...</p>
                    <p>Points: 252</p>
                    <p># Comments: 115</p>"
```
**正文一个字都没有**。LLM 拿到的"描述"其实只是元信息。等于模型只能凭标题猜，准确率自然差。

**这是当前 summary 总写得隔靴搔痒的根因**，比 prompt 工程问题严重得多。

**修复**（按工作量排序）：
- HN：URL 一般指向博文 → 顺手 fetch + readability 抽正文（500ms/条，加 cache）
- Reddit：取 `entry.summary` 实际是帖子正文，但被 `<!-- SC_OFF -->` 包裹，要解 HTML
- arXiv：`entry.summary` 是 abstract，直接用
- GitHub：拉 README.md 前 2KB（一次 raw.githubusercontent.com 请求）

不抓正文，后面 prompt 怎么改都是猜。

### 2.3 Prompt 里枚举分隔符=输出歧义
```
"category": "llm|agent|rag|mcp|evaluation|deployment|security|other"
```
模型把 `|` 学成了输出分隔符 → 出现 `agent|evaluation`、`llm|agent|rag`。

→ 改用列表式 prompt + JSON schema 约束：
```
"category": "选择以下其中一个：llm / agent / rag / mcp / evaluation / deployment / security / other"
```
再由 organizer 校验为单值，多值意味着模型不确定，应回到 reviser。

### 2.4 单条调用，浪费 batch 红利
现在是 for-loop 每条一次 API 调用。一批 20 条等于 20 次往返。
- 改用 batch：一次 prompt 给 5 条，让模型返回 array（成本 ~3× 节省）
- 或更激进：DeepSeek/Qwen 都支持并发 N=4，loop 内开 asyncio gather

### 2.5 `relevance_score` 与 prompt 没有锚点
prompt 直接给 `"relevance_score": 0.8` 作为示例，模型就默认 0.8 起步 →
**实际分布 0.80–0.95，方差极小**，对排序完全无用。

修法：
- 在 prompt 里给出 0.2 / 0.5 / 0.8 / 1.0 的**锚点示例**（4 个不同水平的内容片段）
- 或者干脆删掉 relevance_score，用 `score (1-10)` 一个维度足矣（信息上等价）

---

## 3. Reviewer 层：抽样 5 条审一批等于不审

```python
# reviewer.py:44
sample = analyses[:5]
```

- 永远取前 5 条（不是随机），评分结果代表的是前 5 条
- 拿这 5 条算出的加权分判定**整批 30 条**通过/不通过
- LLM 失败时（exception path）自动 `passed=True`

这相当于"审核走过场"。看一下成品的 `score` 分布（mean 7.46, 92% 落在 7-8），可以证实模型根本没在细分。

**修复方案（按力度）**：

| 力度 | 做法 | 成本 |
|---|---|---|
| 弱 | 改抽样为均匀采样（间隔取） | 0 |
| 中 | 每条独立审，score < 阈值的进 reviser | 单条多一次 LLM 调用 |
| 强 | 取消通用 reviewer，**让 reviewer 只做拒绝判断**（reject reasons：旧重复、广告、噪声、来源不可靠）| 每条 1 次调用，但 prompt 短 |

我推荐**强方案 + 把"打分"这件事还给 analyzer**。理由：reviewer 的"五维加权"在 analyzer 阶段就该决策，第二次让模型自己审自己等于打折扣。reviewer 更适合做：
- 跨条对比（这一批里哪条最值得读）
- 拒绝判断（明显应淘汰的）
- 一致性检查（tag 和 summary 互证）

### 3.1 Reviewer 异常自动通过，破坏门控
```python
except Exception as error:
    weighted_score = 7.0
    passed = True   # ← 失败=通过，反人性
```
当下游不稳时，会有"幽灵高分"条目入库。
→ 至少改成 `status=draft` + 不进 `index`，让人工兜底。

---

## 4. Organizer 层：去重粒度太粗

### 4.1 URL 全等去重 ≠ 语义去重
URL 不同但内容相同的情况很常见：
- HN 上 arxiv.org/abs/X 和 arxiv.org/pdf/X.pdf
- Reddit 转发同一篇博文，URL 是 reddit.com/r/.../link/...
- Twitter/X 短链 / utm 参数差异

**修复**：
- 规范化 URL（去 utm、统一 http/https、arxiv.org/abs vs pdf）
- 标题相似度（rapidfuzz）+ URL 域名匹配，>0.85 视为同条
- 或一步到位：title embedding + cosine（这一步用上之前没用的 embedding 模型）

### 4.2 没有"再回看"机制
当前是 append-only：今天的 doc 不再被复看。
→ AI 领域信息半衰期非常短，2 周前判断为"中等价值"的内容今天可能因为新事件变成"必读背景"。建议加 `revisit` 字段：

```json
{
  "first_seen": "2026-05-02",
  "last_referenced": "2026-05-12",   // 被新一批的相似条目命中过几次
  "reference_count": 3,
  "promoted": false                   // 经多次命中后人工或规则升级
}
```

### 4.3 缺一个"价值升降级" pass
每周扫一次 articles/，对 reference_count 高的条目升 `score`，对 30 天未被相似命中、relevance < 0.85 的条目降级到 `archived`。
→ 让知识库主动遗忘，不要无限堆积。

---

## 5. 验证层：当前只有格式校验，缺事实校验

`hooks/validate_json.py` 检查的是字段存在性，`check_quality.py` 检查的是字符长度和"空洞词"。两个 hook 没有任何检查能识别**事实正确性**或**摘要是否忠于原文**。

### 5.1 推荐加四类校验

**A. 摘要-原文一致性（faithfulness check）**
- 抽取摘要里的数字、专有名词
- 在 raw_description 里 grep，缺一个就标记
- 不需要 LLM，正则就行

**B. 链接可达**
- 写入前 HEAD 一次 source_url，4xx/5xx 标记 `link_status: broken`
- 配 cron 每周回扫，broken 自动 archived

**C. 标签互证**
- summary 中含 "RAG"/"检索增强" 但 tags 没 `rag` → fail
- 已有 VALID_TAGS 表，反查关键词→必须有的 tag

**D. 重复探测**
- 写入时算 title trigram + URL host
- 与最近 30 天比对，> 0.9 相似度，进 `pending_review/duplicates/`

### 5.2 验证应该分**写入硬阻塞**与**事后软标记**
- 硬阻塞（写不进去）：A, B 这种结构性错误
- 软标记（写入但加 flag）：模型分歧、低分、可疑重复 → 让 UI 显示警示，不要静默丢失

---

## 6. 推荐执行顺序（按 ROI 排序）

每一步都是孤立可上线，互不阻塞。

| # | 改动 | 工作量 | 收益 | 解决症状 |
|---|---|---|---|---|
| 1 | collector.py 修 per-source limit（1.1） | 10 行 | 高 | 源覆盖偏窄、95/140 来自 r/ML |
| 2 | RSS 抓正文：HN 走 readability、Reddit 解 SC_OFF、arXiv 用 summary（2.2）| 半天 | **最高** | summary 隔靴搔痒、模型只能猜 |
| 3 | 加前置规则过滤（2.1） | 1 小时 | 高 | LLM 浪费在垃圾条目上 |
| 4 | reviewer 改为按条审核 + 失败不放行（3, 3.1） | 1 小时 | 中 | 门控形同虚设 |
| 5 | analyzer prompt 修枚举歧义 + relevance 锚点（2.3, 2.5） | 30 分钟 | 中 | category 多值、score 全 7-8 |
| 6 | GitHub query 分桶 + collector 跨日去重（1.3） | 2 小时 | 中 | 头部仓库反复采 |
| 7 | URL 规范化 + 标题相似度去重（4.1） | 2 小时 | 中 | 假新条目 |
| 8 | 摘要-原文 faithfulness 校验（5.1A） | 半天 | 中 | 摘要可能编 |
| 9 | 链接可达性校验 + 周扫（5.1B） | 1 小时 + cron | 低 | 死链 |
| 10 | 价值升降级 pass（4.3） | 半天 | 长期价值高 | 知识库无限堆积 |

第 2 步是真正的破局点：**没有正文，所有下游都在补救**。把抓正文做好，prompt / reviewer / 校验都会自然变好。

---

## 7. 不建议做的事

- **不要立刻接更多源**：源覆盖问题是因 collector bug 导致的（1.1），不是源不够。先修，再观察。
- **不要在 prompt 上无限叠词**：当前 summary 烂的根因是输入烂（无正文），不是 prompt 不够好。
- **不要给 reviewer 加更多维度**：5 维已经太多。建议合并到 3 维（accuracy / depth / novelty）。
- **不要急着上 embedding 去重**：先把 URL 规范化做掉（4.1 第一档），可能就解决了 80% 重复。
- **不要保留"失败自动通过"路径**：宁可阻塞流水线，也别让脏数据混入。
