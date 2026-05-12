# AI Knowledge Base UI

Notion-like 知识库管理面板，用于浏览、筛选、编辑和批量管理知识条目。

## 启动

```bash
uv run python ui/app.py
```

浏览器打开 http://localhost:5050

## 功能

- **浏览**：卡片列表，分页，排序（更新/发布/评分/标题）
- **筛选**：左侧栏按来源、分类、标签、状态过滤
- **搜索**：实时搜索标题与摘要
- **详情抽屉**：点击标题展开右侧面板，查看完整内容
- **多选批量操作**：勾选卡片 → 底部浮现操作栏，支持批量打标签、改分类、改状态、归档、删除
- **统计面板**：顶部显示总数、来源数、标签数

## 技术栈

- 后端：Flask + JSON 文件读写
- 前端：Vanilla JS + CSS（无框架依赖）
- 数据：直接读写 `knowledge/articles/*.json`

## API 端点

```
GET    /api/articles              # 列表（支持 filter/sort/pagination）
GET    /api/articles/<id>         # 详情
PATCH  /api/articles/<id>         # 更新
DELETE /api/articles/<id>         # 删除
POST   /api/articles/batch        # 批量操作
GET    /api/stats                 # 统计
GET    /api/filters               # 筛选枚举值
```
