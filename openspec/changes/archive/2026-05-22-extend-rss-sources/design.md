## Context

`workflows/collector.py` 中的 `collect_rss(limit)` 用单一全局上限跨所有源共享配额，第一个源拿完就轮不到后面的源。`organizer.py` 在去重时只对 `source_url` 做精确匹配，无法识别"同一篇文章在多个 RSS 源上以不同 URL 出现"的转载场景。`rss_sources.yaml` 当前只 12 个源，覆盖面有限。UI (`ui/app.py`) 目前没有源管理视图。

候选源经过 `webfetch` 验证（gist 精选 + aihot 上游交叉），已确认 18 个新源可用，3 个失败的（anthropic-engineering、qwen-blog、hf-papers）和噪声大的 ithome 全部放弃。

## Goals / Non-Goals

**Goals:**
- 多源场景下保证每个源都有保底配额，靠后的源不被前面吃光
- 跨源识别转载内容，避免重复 LLM 调用
- 提供 18 个高信号新源，覆盖官方一手 / 研究 / 个人分析师 / 工程师 / 新闻聚合
- UI 支持在不改动 yaml 文件的情况下临时禁用某个源

**Non-Goals:**
- 不引入"信源评分 / 来源权威分"等额外信号
- 不引入 HTML 抓取能力（坚持只接受标准 RSS/Atom）
- 不在本次实现 source CRUD（增/删/改 URL），只做 toggle enabled（L1）
- 不实现"按 category 路由到不同 reviewer"
- 不做相似度去重（minhash / embedding），仅做规则化指纹
- 不改动 `analyzer` / `reviewer` / `organizer` 节点

## Decisions

### Decision 1: per-source 配额放在 yaml，运行时不可覆盖

**选择**：在每个 source 条目里新增 `per_source_limit` 字段（默认 5），CLI 仅传"全局上限"。

**理由**：保持"配置在 yaml"的现有约定。CLI 参数已经够多，不想再加 `--per-source`。开发期临时压低某个源的产量可以直接编辑 yaml。

**替代方案**：CLI 覆盖（如 `--per-source openai-blog=2`）。否决：API 表面变复杂，受益场景少。

### Decision 2: 配额冲突时用"比例缩放"，不用公平轮询

**选择**：
```
Σ = sum(src.per_source_limit for src in enabled)
if Σ <= global_cap:
    actual[src] = src.per_source_limit
else:
    scale = global_cap / Σ
    actual[src] = max(1, ceil(src.per_source_limit * scale))
```

**理由**：
- yaml 里已经用 `per_source_limit` 表达了"我希望这个源占多大比重"，比例缩放最忠于这个表达
- `ceil` + `max(1, ...)` 保证小源不被砍到 0
- 实现就是一行算式，比轮询简单

**替代方案**：
- 顺序硬截断：靠后的源饿死，否决
- 公平轮询：实现稍复杂，且会忽略"hn-best 应该比 garymarcus 多收"的意图，否决

**已知偏差**：`ceil` 会让总数稍微超过 `global_cap`（最多多出 `len(enabled)` 条），可接受。

### Decision 3: 内容指纹去重 = `normalize(title) + domain(url)`

**选择**：在 `collect_rss` 末尾对收集到的 items 计算 fingerprint，跨源、跨历史去重。fingerprint 公式：

```python
def fingerprint(title: str, url: str) -> str:
    norm = re.sub(r"[^\w\u4e00-\u9fff]+", "", title.lower())
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    return f"{domain}|{norm}"
```

**理由**：
- 同源转载（如 HN 转 SW）：domain 不同，不去重 → ✅ 我们想要的，HN 标题可能加了上下文
- 同标题不同站（如多家媒体报 Claude 4 发布）：domain 不同，不去重 → ✅ 多视角有价值
- 真正想挡的：同源被 RSS 重复推送（feed 修改导致 URL 微变） → ✅ 此时 domain + 归一化标题命中
- 简单、可测、解释得清

**替代方案**：
- 只 `normalize(title)`：误杀严重，不同公司同标题的官宣会撞
- title + URL 路径段：路径变了就漏，不可靠
- summary minhash：要在 collector 阶段抓全文/摘要，超出本次范围

**持久化**：fingerprint 只存内存（每次 run 时扫一遍现有 `articles/*.json` 重建）。简单胜过加索引文件。

### Decision 4: UI 走 L1（toggle），不做 CRUD

**选择**：
- `GET /api/sources` → 返回 yaml 全量 + 每源近 7 天采集数
- `PATCH /api/sources/<slug>` body `{"enabled": bool}` → 改 yaml 写回
- 前端：一张表格，每行 toggle + 7d count

**理由**：用户真实诉求 80% 是"这个源太吵，关掉"。CRUD（加源 / 改 URL）yaml 手编更快，反而 UI 拖累。

**替代方案**：CRUD（L2）。否决：超出 2 天预算，且收益边际。

### Decision 5: yaml 写回用"tmp + rename"原子替换

**选择**：
```python
tmp = path.with_suffix(".yaml.tmp")
tmp.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
os.replace(tmp, path)
```

**理由**：避免半写状态损坏配置文件。不上锁，因为 UI 是单用户、低频写。

### Decision 6: 18 个新源 + 放弃 4 个

新增（已 webfetch 验证）：

| Category | Slug | URL |
|---|---|---|
| industry | deepmind-blog | `https://deepmind.google/blog/rss.xml` |
| analyst | simonwillison | `https://simonwillison.net/atom/everything/` |
| analyst | garymarcus | `https://garymarcus.substack.com/feed` |
| analyst | dwarkesh | `https://www.dwarkeshpatel.com/feed` |
| analyst | minimaxir | `https://minimaxir.com/index.xml` |
| analyst | gwern | `https://gwern.substack.com/feed` |
| analyst | geohot | `https://geohot.github.io/blog/feed.xml` |
| analyst | tomtunguz | `https://tomtunguz.com/index.xml` |
| engineering | antirez | `http://antirez.com/rss` |
| engineering | mitchellh | `https://mitchellh.com/feed.xml` |
| engineering | matklad | `https://matklad.github.io/feed.xml` |
| engineering | rachelbythebay | `https://rachelbythebay.com/w/atom.xml` |
| engineering | eli-thegreenplace | `https://eli.thegreenplace.net/feeds/all.atom.xml` |
| engineering | fabiensanglard | `https://fabiensanglard.net/rss.xml` |
| engineering | lucumr | `https://lucumr.pocoo.org/feed.atom` |
| engineering | hillelwayne | `https://buttondown.com/hillelwayne/rss` |
| news | the-decoder | `https://the-decoder.com/feed/` |
| research | arxiv-cs-cl | 已存在，改 `enabled: true` |

放弃：`anthropic-engineering`（404）、`qwen-blog`（404）、`hf-papers`（502，第三方镜像）、`ithome-ai`（AI 含量 < 30%，引入会触发引入 `rules` 字段，超出当前预算）。

## Risks / Trade-offs

- **[风险] fingerprint 误杀同源不同文**：例如 simonwillison 的两篇标题里都含 "GPT-5"，去掉标点和空格后归一化结果接近。
  → **缓解**：归一化只去标点和空格，不去关键词。两篇真正不同的内容，标题至少会差几个字，归一化结果不会完全一致。接受小概率误杀。

- **[风险] yaml 被 UI 改写后注释丢失**：`yaml.safe_dump` 不保留原有注释。
  → **缓解**：当前 yaml 的注释只在文件顶部说明用途。重写时保留顶部注释字符串硬编码进 dump 函数。或者更简单：接受丢失，文件顶部的说明字符串记在 Python 常量里。

- **[风险] 新增 18 个源后单次 run 时间显著变长**：每源 HTTP 20s 超时，最坏情况 32 * 20 = 640s。
  → **缓解**：当前 `collect_rss` 顺序 fetch；本次不改并发模型（避免越界）。但要把 `httpx.Client` timeout 从 20s 降到 10s，并加 `connect_timeout=5s`，最坏情况降到 ~320s。如果实测仍慢，下一个 change 再引入 `asyncio.gather`。

- **[风险] reddit / hn 的 fingerprint 会跟原文撞**：如 LocalLLaMA 转 SW 博客，HN 转 OpenAI 博客。
  → **设计上不挡**（参见 Decision 3）：domain 不同就不去重，因为转载平台的标题/讨论本身有信息量。

- **[Trade-off] per_source_limit 默认 5 偏宽松**：算上 18 个新源后总和会到 ~113，全局 `--limit 20` 时缩放比例约 1:5.7，多数小源会被砍到 1 条。
  → **接受**：第一次 run 后看实际分布再调整 yaml。
