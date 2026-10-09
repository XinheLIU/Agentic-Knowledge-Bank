# Cognitive compounding — draft input

Last updated: 2026-10-08

Status: draft, not designed. This is the preserved material for **step 2 (cognitive compounding)**, extracted from the retired `TODO.md` on 2026-10-08 by wayfinder ticket **Remove unrelated legacy**. The wiki effort deliberately defers this design; nothing here is a commitment or a specification. Text is kept in its original language.

The concept-wiki effort (steps: `archive → materials → notes → wiki`) is goal 1, **cognitive asset accumulation**. This file is the input to goal 2, **cognitive compounding**.

## The 泛读 / 精读 learning model

From `## thinking about learning` in the retired `TODO.md`. A three-way split of learning time; the percentages are the original author's intent, not a measured target.

### 1. 泛读 — 新知识输入 (30%) ***

- 泛读 一个本子（one notebook for broad reading）
  1. 设置 checklist
  2. 拓展 3–5 个信息源，信息源评分
  3. 每周选一个单一信息源 deep dive in，阅读最近 6 个月到 1 年

### 2. 精读 — 知识体系整理 (40%)，临界知识 knowledge graph

1. 泛读综述类专栏/书，画知识图谱（top-down）或学习指南/新人文档
2. AI 问答和深入，整理文献、作者（人）、核心贡献（李沐读论文的方法）
3. 和自己的经历关联，决定产出（写作或深度 dive in）
4. 知识体系拆分 — 决定是否需要深度 dive in

### 3. 精读 — 深度 dive in (30%)

1. 立项：明确 why am I learning this (what do I get)
2. What do I need to learn — 设置核心任务（with AI prompts）
3. 总计：沉淀到知识库 和 动手项目（with AI prompts）
4. 产出 → 积累 → 整体整理（思考）

## The 认知复合引擎 epic

From `## thinking` in the retired `TODO.md`: "史诗故事：构建认知复合引擎，实现战略级知识复合与决策加速". As an AI practitioner with information overload, I want to turn the system from an "AI 新闻阅读器" into a "认知复合引擎", so that it systematically structures information, distills strategic insight, and ultimately accelerates my decisions and cognitive iteration.

### 核心用户故事

**一、信息结构化与知识复合**

1. **结构化知识图谱构建** — 系统能自动跟踪和分析 AI 领域的前沿动态，并构建知识图谱连接不同信息源中的概念、技术和趋势。这样可以停止碎片化阅读，直接获得结构化认知网络，快速定位关键联系和知识空白。
2. **战略级趋势提炼** — 系统每周能从海量信息中提炼出 3–5 个战略级趋势（如基础设施层变化、瓶颈转移等），并附上可行动的洞察建议。这样可以聚焦高信号信息，避开噪音，优化学习优先级，做出更具前瞻性的战略决策。

**二、个性化认知层与智能过滤**

3. **动态个性化过滤** — 系统能学习我的兴趣、框架、战略方向和技术栈，并自动过滤信息流，只呈现与我核心关注点相关的高价值内容。这样可以节省筛选时间，确保接触到的信息能直接强化我的专业领域或填补认知缺口。
4. **认知模式识别与预警** — 系统能识别并预警我所在领域的潜在范式转变或技术瓶颈（如"工具生态转向基础设施层"）。这样可以提前调整研究方向或资源投入，抓住结构性机会，降低被颠覆的风险。

**三、决策支持与行动指南**

5. **战略优先级仪表盘** — 系统提供一个可视化仪表盘，显示当前最重要的技术方向、投资领域和风险预警，并基于我的上下文自动更新。这样可以快速同步团队或调整个人学习计划，确保资源投入与外部变化同步，提升决策响应速度。
6. **可执行洞察库** — 系统能积累和结构化存储我的所有高价值洞察、趋势分析和决策依据，支持快速检索和关联。这样可以建立个人知识资产，避免重复分析，并在需要时快速调用历史洞见支持新决策。

**四、长期愿景**

7. **认知加速与思维迭代** — 作为终身学习者，系统能通过持续的知识复合，逐步优化我的思维模型和决策框架，最终加速我的认知迭代速度。这样可以在快速变化的 AI 领域保持领先，形成独特的战略视角和竞争优势。

### 非功能性需求与关键设计

- 系统需实现 `信息 → 观察 → 模式 → 抽象 → 框架 → 决策` 的自动转化流程。
- 支持多模态输入（文本、代码、数据、演示等），统一结构化处理。
- 高度可配置：允许用户定义战略优先级、技术栈和过滤规则。
- 提供可解释性：所有趋势和推荐需附带证据链和置信度评分。

### 验收标准示例

- 用户每周接收的趋势报告包含 ≥3 个可验证的战略级洞察，覆盖不同技术栈。
- 用户反馈的"无关信息"在后续推荐中被自动过滤，准确率提升至 90% 以上。
- 知识图谱支持 3 级深度关联查询，并展示技术演进路径。

### 价值主张

通过将信息转化为可复用的战略资产，帮助用户从"被动追赶趋势"转向"主动塑造认知"，最终在专业领域建立深厚护城河。

> 备注（原文）：每个用户故事可根据开发阶段细化为更小的任务或子故事，并关联具体的技术实现模块（如知识图谱构建、趋势检测算法、个性化推荐引擎等）。

## What step 2 must decide

Not settled here. The wiki effort deliberately leaves these to a later design:

- **Relationship to the wiki.** Compounding operates on the published wiki and the source registry; it does not re-derive them. Whether it lives in Agentic-Knowledge-Bank, Information Assistant or a third product is open.
- **Where trend extraction belongs.** Stories 1–2 (knowledge-graph construction, weekly strategic trends) overlap the wiki's cross-topic surface and Information Assistant's source pipeline. The boundary is undecided.
- **Personalization and filtering.** Stories 3–4 read learner/user state (interests, frameworks, tech stack) and flag paradigm shifts. That state belongs to the user, not to this repository — the wiki's invariant "AKB never writes learner state" still applies.
- **The dashboard and insight library.** Stories 5–6 are a presentation surface and a durable insight store; neither has an owner.
- **The transformation chain.** `信息 → 观察 → 模式 → 抽象 → 框架 → 决策` is the epic's spine and the first thing a step-2 design must make concrete or reject.
