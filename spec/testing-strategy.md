# AI 知识库 · Testing Strategy
> Last updated: 2026-05-06

## Summary

Testing is split into two separate lanes:

- `non_llm`: deterministic tests for code behavior with mocked or avoided LLM calls
- `llm_e2e`: real-provider end-to-end verification of the LangGraph workflow

These two lanes serve different goals and should not be conflated.

## 1. Non-LLM Lane

### Purpose
- fast feedback during development
- deterministic failures
- broad coverage of logic, routing, normalization, hooks, and persistence rules

### Included
- hook validation and quality scoring
- model-client parsing/retry/env selection with mocked provider behavior
- RSS and GitHub fetch normalization with mocked HTTP
- workflow route and policy checks
- organizer and human-flag persistence behavior
- analyzer/reviewer/reviser node behavior with mocked LLM responses
- graph compile/invoke smoke test with mocked nodes
- notebook JSON smoke test

### Command

```bash
uv run pytest -q -m non_llm
```

or

```bash
uv run pytest -q -m "not llm_e2e"
```

## 2. Real-LLM E2E Lane

### Purpose
- verify that the configured provider actually works
- verify that the LangGraph workflow executes end-to-end with real LLM calls
- verify that published outputs pass repository hooks

### Success Criteria
- workflow completes without entering `human_flag`
- at least one article is published
- generated article JSON passes `validate_json.py`
- generated article quality is at least grade `B`

### Isolation
- writes to temporary article and pending-review directories
- does not pollute `knowledge/articles/`
- does not rely on the daily production collection workflow

### Required Env Vars
- `LLM_PROVIDER`
- provider-specific API key:
  - `DEEPSEEK_API_KEY`
  - `DASHSCOPE_API_KEY`
  - `OPENAI_API_KEY`
- `GITHUB_TOKEN`

### Command

```bash
uv run pytest -q -m llm_e2e
```

If provider credentials are absent, the test is skipped instead of failing the default suite.

## 3. CI Strategy

### Production workflow
- `.github/workflows/daily-collect.yml`
- runs the real workflow for collection and publishing
- not the main testing workflow

### Real-LLM verification workflow
- `.github/workflows/llm-e2e.yml`
- triggered manually and on a separate schedule
- runs only the `llm_e2e` lane

## 4. Tradeoffs

- `non_llm` gives confidence in code behavior
- `llm_e2e` gives confidence in external provider integration
- neither replaces the other
- real-LLM tests are slower, cost money, and can fail due to provider instability

## 5. Operational Rule

When changing prompts, state shape, workflow routing, article contract, or provider handling:
- run `non_llm` first
- run `llm_e2e` before trusting the change in production
