# WebbGPT 知识库指南

> 原始数据如何获取、处理成向量嵌入、以及日常维护方法。

---

## 1. 架构概览

```
原始数据源                  中间格式                   向量索引
──────────                  ────────                   ────────
webb.org (111 页)    ──►  data/scraped/*.json  ──►  ChromaDB
  通过 scraper.py           (纯文本)                  935 个 chunks
                                                      768 维向量
PDF 文件 (9 个)      ──►  data/scraped/*.json  ──►  (同一索引)
  通过 pdf_loader.py        (纯文本)
```

整个流程分三个阶段：
1. **获取** — 从网站和 PDF 抓取原始内容
2. **处理** — 文本分块 + 生成嵌入向量
3. **服务** — 查询时检索相关分块

---

## 2. 数据来源

### 2.1 网站 (webb.org)

| 项目 | 详情 |
|------|------|
| **脚本** | `ingest/scraper.py` |
| **方法** | `requests` + `BeautifulSoup`（仅限静态 HTML） |
| **页面列表** | 硬编码自 `webb.org/view-our-sitemap` |
| **已抓取** | 111 个页面（69 静态页 + 33 运动队页 + 9 其他页面） |
| **输出** | `data/scraped/web_*.json` |
| **局限** | 无法抓取 JavaScript 动态渲染的内容（AJAX 球队名单、日历事件、课程详情页） |

**各版块覆盖情况：**

| 版块 | 页数 | 内容 |
|------|------|------|
| 招生 (Admission) | 13 | 申请方式、学费、助学金、校园参观、常见问题 |
| 关于 (About) | 8 | 使命、领导层、文化、新闻、通讯录 |
| 学术 (Academics) | 13 | 核心课程、各学科、教师、课程目录、Alf 博物馆 |
| 学生生活 (Student Life) | 10 | 宿舍、餐饮、社团、健康、周末活动 |
| 体育 (Athletics) | 38 | 33 个运动队页面（教练、赛程）+ 5 个综合页（CIF、记录、暑期训练） |
| 夏校 (Summer) | 3 | 项目介绍 |
| 捐赠 (Giving) | 7 | 捐赠方式、基金 |
| 校友 (Alumni) | 5 | 活动、奖项 |
| 其他 | 14 | 首页、隐私政策、录取名单、校长致辞、升学指导简介、教师奖项、迎新日程、反歧视政策、比赛日程 |

**网站中未能抓取的内容：**

| 内容 | 原因 | 替代方案 |
|------|------|---------|
| 课程详情页 (`/page/curriculum-detail?...`) | Blackbaud CMS 返回 HTTP 403 | Course Catalog PDF 已覆盖所有课程 |
| 日历事件 | JavaScript 动态渲染（Blackbaud CMS） | Travel Dates PDF 覆盖关键日期；聊天机器人引导至 webb.org/calendar |
| 运动队名单（学生姓名） | JavaScript 动态渲染 + 学生隐私 (FERPA) | 教练姓名和赛程已抓取；聊天机器人引导至 webb.org/athletics 查看名单 |
| 新闻文章 | 动态页面，时效性强 | Q&A 价值低 |
| 教师详细简介 | Meet-our-faculty 页面只显示姓名/职位/学历（无展开式简介） | School-leadership 页面的简介已抓取 |

### 2.2 PDF 文档

| 项目 | 详情 |
|------|------|
| **脚本** | `ingest/pdf_loader.py` |
| **方法** | `pypdf` 文本提取 |
| **源文件夹** | `data/pdfs/` |
| **输出** | `data/scraped/pdf_*.json` |

**当前 PDF 清单：**

| PDF 文件 | 内容 | 大小 | 年份 | 重要性 |
|----------|------|------|------|--------|
| `2025-26 Student Handbook Final.pdf` | 校规、纪律、宿舍规则、请假、荣誉准则、作息时间 | 209,931 字符 | 2025-26 | 关键 |
| `course_catalog_2026-27.pdf` | 所有课程描述、先修要求、毕业要求 | 64,989 字符 | 2026-27 | 关键 |
| `2025-2026_college_guidance_brochure-output.pdf` | 升学指导简介、SAT 分数、毕业要求、录取去向 | 4,777 字符 | 2025-26 | 高 |
| `Travel Dates 2026-2027.pdf` | 入住日期、假期、到离校时间 | 2,014 字符 | 2026-27 | 高 |
| `Travel Dates FY26.pdf` | 同上（当年） | 1,775 字符 | 2025-26 | 高 |
| `Device Guidelines.pdf` | 新生笔记本电脑要求 | 1,429 字符 | 2025 | 中 |
| `FAQ_TechOffice.pdf` | WiFi、打印、杀毒软件、技术支持 | 6,128 字符 | 2025 | 中 |
| `WebbAUP2025.pdf` | 技术可接受使用政策 | 4,682 字符 | 2025 | 中 |
| `RTPWebb.pdf` | 网络使用规范 | 5,626 字符 | 2025 | 中 |

### 2.3 外部资源链接（不索引，仅在回答中以链接形式提供）

| 资源 | 网址 | 触发条件 |
|------|------|---------|
| DHS：国际学生旅行指南 | studyinthestates.dhs.gov/... | F-1 签证、国际学生旅行 |
| ICE：F 签证再入境 | ice.gov/sevis/travel | 签证再入境 |
| DHS：Study in the States | studyinthestates.dhs.gov | 国际学生通用信息 |
| DHS：旅行提醒与文件 | studyinthestates.dhs.gov/.../travel-reminders | 旅行文件 |

---

## 3. 处理流程

### 3.1 JSON 中间格式

scraper.py 和 pdf_loader.py 都输出相同的 JSON 格式：

```json
{
  "url": "https://www.webb.org/admission" 或 "local://pdf_handbook.json",
  "title": "页面或文档标题",
  "content": "全部文本内容...",
  "scraped_at": "2025-03-22T..."
}
```

所有 JSON 文件保存在 `data/scraped/`。索引构建器不区分网页来源还是 PDF 来源。

### 3.2 文本分块

**脚本：** `rag/build_index.py` — `chunk_text()` 函数

**算法：** 段落感知分块

```
1. 按段落边界 (\n\n) 分割文本
2. 合并连续的小段落，直到接近 CHUNK_SIZE
3. 如果单个段落超过 CHUNK_SIZE，按字符数分割
4. 在每个分块前面添加上一个分块的末尾 CHUNK_OVERLAP 个字符
```

**参数（当前值）：**

| 参数 | 值 | 选择原因 |
|------|---|---------|
| `CHUNK_SIZE` | **1,200 字符** | 足够保留一条完整政策及其例外情况。测试过：800 会导致上下文碎片化；1,500 浪费 token 预算。 |
| `CHUNK_OVERLAP` | **250 字符** | 防止分块边界处丢失信息。对 Handbook 中规则和处罚分跨两段的情况至关重要。测试过：100 会漏掉细节；400 导致过多重复。 |

**为什么用段落感知分块（而不是固定长度）？**

固定长度分割会在字符位置 N 处截断，可能在句子中间切开，破坏政策文本的含义。段落感知分块尊重 Handbook 和课程目录中的自然章节分隔，保持相关规则在同一个分块中。

**统计数据：**

| 指标 | 值 |
|------|---|
| 总分块数 | 935 |
| 平均分块长度 | ~900 字符 |
| 数据源 | 120 个 JSON 文档（111 网页 + 9 PDF） |

### 3.3 嵌入向量生成

| 参数 | 值 | 原因 |
|------|---|------|
| **模型** | `gemini-embedding-001` | 免费额度大；原生多语言支持（中英韩日等）；768 维紧凑但准确 |
| **维度** | 768 | 模型固定 |
| **速率控制** | 每次调用间隔 `sleep(0.55)` | 付费层允许 ~110 请求/分钟；0.55 秒保持在限制内 |
| **重试逻辑** | 5 次重试，指数退避（60秒、120秒...） | 处理 429 限流错误 |
| **批次大小** | 每批 10 个分块 | ChromaDB add() 批次；不影响嵌入 API（逐个调用） |

**为什么选 Gemini 而不是 OpenAI？**

| 因素 | Gemini embedding-001 | OpenAI text-embedding-3-large |
|------|----------------------|-------------------------------|
| 维度 | 768 | 3,072 |
| 质量 (MTEB) | ~63 | ~64 |
| 费用 | 免费层：1,500 请求/天 | $0.13 / 百万 token |
| 多语言 | 原生支持 | 良好 |
| 决策 | **选用** — 935 个分块的小库，质量差异可忽略；成本为零 |

### 3.4 向量存储 (ChromaDB)

| 参数 | 值 |
|------|---|
| **数据库** | ChromaDB（持久化，本地） |
| **距离度量** | 余弦相似度 (`hnsw:space: cosine`) |
| **集合名称** | `webb_knowledge` |
| **存储路径** | `chroma_db/` |
| **断点续传** | 检查每个文件的第一个分块 ID；跳过已索引的文档 |

**为什么选 ChromaDB？**

- 零基础设施（不需要外部数据库服务器）
- 持久化到磁盘（重启不丢失）
- 935 个分块轻松放入内存
- 部署到 Render 免费层（磁盘占用 34 MB）

---

## 4. 检索流程（查询时）

**脚本：** `rag/query.py`

### 4.1 多查询扩展

```
用户问题（任意语言）
  │
  ├────────────────────────────────────┐
  │                                    │
  ▼                                    ▼
Claude Sonnet → 3 个英文搜索查询       原始问题（原文不变）
  │                                    │
  ▼                                    ▼
模式匹配 → 话题补充（0-6 个）          Gemini 嵌入（原生多语言）
  │                                    │
  ▼                                    ▼
所有查询 → Gemini 嵌入 → ChromaDB     ChromaDB top-5（+0.05 分数加成）
  │                                    │
  └─────────── 合并 & 去重 ────────────┘
                    │
                    ▼
         按分数排序 → 取前 20 个语义分块
                    │
                    ▼
         关键词兜底 → 跨章节术语
                    │
                    ▼
         20 个语义 + 关键词分块 → Claude Sonnet
```

### 4.2 跨语言检索设计

> **给后续开发者的关键提示：** 知识库是英文的，但用户会用中文、韩文、日文、越南文等提问。修改检索流程前，务必理解"两层翻译损失"问题。

**问题 — 两层翻译损失：**

当用户问"Webb的学费是多少？"时，系统需要将其转换为英文搜索词。这涉及两步转换，每步都可能丢失信息：

```
用户："Webb的学费是多少？"
   ↓ 第1层：LLM 翻译（有损）
expand_query() → ["Webb tuition cost", "annual fees", "boarding tuition"]
   ↓ 第2层：嵌入（准确）
Gemini embedding → 向量搜索 → 结果
```

第1层（LLM 翻译）是漂移发生的地方。例如，口语化的"周末能不能出去玩？"可能被翻译成"weekend recreation"，而不是 Webb 专用的"weekend pass"。

**解决方案 — 同时搜索原始问题：**

Gemini 嵌入模型（`gemini-embedding-001`）是**原生多语言**的。它可以直接将"学费"（中文）和"tuition"（英文）映射到相近的向量空间，无需翻译。通过同时搜索原始问题和英文扩展查询，我们获得：

1. **原始问题搜索** — 利用多语言嵌入直接匹配，无翻译损失，+0.05 分数加成
2. **英文扩展查询** — 覆盖不同角度和 Webb 专用术语
3. **话题补充** — 保证跨章节政策内容

**为什么只扩展 3 个查询（而不是 5 个）：**

5 个扩展时，原始问题只贡献 1/6 的搜索结果（30 个中的 5 个）。如果英文翻译偏了，它们会"淹没"原始问题的正确结果。3 个扩展时，原始问题贡献 1/4 的结果，让多语言嵌入有更大的权重。

**为什么用 Sonnet 扩展（而不是 Haiku）：**

Sonnet 从非英文输入生成英文搜索词的质量显著优于 Haiku。Haiku 在翻译时经常丢失 Webb 专用术语（如把"过夜假"直译，而不是映射到"overnight pass"）。

**测试结果（跨语言 fact coverage）：**

| 语言 | Fact Coverage | 测试数 |
|------|-------------|--------|
| 英文 | 100% | 8 |
| 中文 | 100% | 8 |
| 韩文 | 83% | 2 |
| 日文 | 100% | 1 |
| 越南文 | 100% | 1 |
| **平均 en↔other chunk overlap** | **63%** | |

测试脚本：`tests/test_cross_language.py` — 测试 8 组多语言问题对，衡量关键事实覆盖率和与英文基准的分块重叠率。

### 4.3 关键检索参数

| 参数 | 值 | 原因 |
|------|---|------|
| `TOP_K_PER_QUERY` | **5** | 4-10 个查询各返回 5 个分块；去重后通常得到 15-25 个唯一分块 |
| `MAX_CHUNKS` | **15** | 上下文覆盖和 token 成本的平衡。15 × ~900 字符 ≈ 13,500 字符，在 Sonnet 上下文窗口内 |
| 原始问题分数加成 | **+0.05** | 确保通过多语言嵌入直接找到的分块（无翻译损失）排名更高 |
| 关键词兜底分数 | **0.6**（固定） | 低于语义结果（~0.7-0.9），排在直接匹配之后但仍会出现 |
| 关键词片段半径 | **前 200 + 后 400 字符** | 足以捕获一条完整规则及其上下文 |

### 4.4 为什么我们不使用 Reranking（重排序）

> **给后续开发者的警告：** 添加 reranker（如 Cohere Rerank、cross-encoder 模型）看起来是显而易见的优化，但在本项目中很可能会**降低**回答质量。修改前请务必阅读本节。

**Reranking** 是一种在初始检索后，用交叉编码器模型对候选分块重新评分和排序的技术，目的是把最相关的内容排到前面。

**为什么在本项目中不需要：**

1. **语料库太小** — 只有 935 个分块，检索后得到 20-35 个候选，生成模型（Sonnet）全部读完。没有必要进一步筛选。Reranking 的价值在于从 1,000+ 个候选中选出 10 个；我们没有这个问题。

2. **多查询扩展已经实现了软重排** — 当同一个分块被多个扩展查询命中时，我们保留最高分。这自然地提升了最相关分块的排名。

3. **关键词兜底分块会被伤害** — 这是最关键的风险。我们的系统使用关键词兜底来保证跨章节政策内容的包含（如 CBO、延长假、校园禁足）。这些分块的语义相似度分数很低（固定为 0.6），因为它们来自 Handbook 的不同章节。Reranker 很可能给它们打低分并排除掉，**破坏我们辛苦建立的跨章节政策覆盖**。

4. **增加延迟** — Reranking API 调用每次增加 1-2 秒，在已经 15 秒的响应时间上雪上加霜。

5. **增加成本和复杂度** — 需要新的 API key（Cohere）或模型依赖，对我们的规模收益甚微。

**何时重新考虑：** 如果知识库增长到 10,000+ 分块（例如添加完整的新闻存档、独立课程页面或多年的 Handbook），检索质量可能下降，reranking 才有价值。届时需确保关键词兜底分块不参与重排（直接透传）。

### 4.5 话题补充与关键词触发器

> **重要局限：** 这些是**硬编码的**模式→查询映射，**不是通用解决方案**。它们是在测试中发现特定的跨章节检索失败后创建的——主要是"过夜假"问题需要从纪律章节拉取 CBO。**目前只覆盖了 4 个话题。** 涉及其他交叉引用政策的问题（例如"残障学生有什么住宿安排？"需要同时拉取学术和住宿两个章节）可能仍会遗漏相关内容。

**它们的作用：** 当用户问题匹配已知话题模式时，系统注入额外的搜索查询并扫描原始文档中的特定术语。这弥补了纯语义搜索无法覆盖的空白——例如，"过夜假"和"Campus Beautification Opportunity"在语义上毫无关联，但 CBO 直接影响请假资格。

**当前话题覆盖（仅 4 个话题）：**

| 话题模式 | 补充查询数 | 搜索的关键词 |
|---------|-----------|------------|
| overnight, pass, 离校, 过夜 等 | 6 个查询 | Campus Beautification Opportunity, extended pass, Reach break pass, campusing |
| discipline, honor, 纪律, 违规 等 | 3 个查询 | Campus Beautification Opportunity, Honor Code, campusing |
| admission, apply, 学费 等 | 3 个查询 | — |
| college, university, 大学, 升学 等 | 4 个查询 | — |

**已知空白（尚未覆盖的话题）：**

- 健康/医疗政策与宿舍规则的交叉引用
- 技术政策与纪律处分的交叉引用
- 体育参赛资格与学术要求的交叉引用
- 助学金与入学条件的交叉引用
- 未来 Handbook 新版中引入的任何新交叉引用

**如何发现新空白：** 运行测试集（`python tests/run_tests.py`），查看低分回答，检查缺失的内容是否存在于 Handbook 的其他章节。如果是，就在 `TOPIC_SUPPLEMENTS` 和 `KEYWORD_TRIGGERS` 中添加新条目。

**为什么硬编码是脆弱的：**

1. 如果 Handbook 改了术语（如"CBO"被重命名），触发器会静默失效
2. 未来 Handbook 中的新跨章节关联不会被自动捕获
3. 为每一种可能的交叉引用都添加覆盖是不现实的——Handbook 有几十条相互关联的政策

**未来改进方向：**

| 方案 | 工作原理 | 权衡 |
|------|---------|------|
| **LLM 两轮检索** | 初始检索后，让 **Sonnet**（非 Haiku）判断："这个问题还需要参考哪些相关政策？"然后进行第二轮检索。选 Sonnet 是因为判断跨章节关联需要较强的推理能力，Haiku 可能漏判。 | +1-2 秒延迟，+$0.003/查询，但能自动发现交叉引用 |
| **索引时打标签** | 建索引时让 LLM（如 Gemini Flash）自动给每个 chunk 标注话题标签（纪律、住宿、学术等）。**不需要人工标注**——LLM 阅读分块内容后自动分类。查询时除语义搜索外按话题检索。 | 需要重建索引（一次性 LLM 成本约 $0.05），但无运行时成本 |

### 4.6 回答生成

| 参数 | 值 | 原因 |
|------|---|------|
| **模型** | `claude-sonnet-4-20250514` | 质量/成本最优；Haiku 测试过但会遗漏交叉引用的政策 |
| **最大 token** | 1,024 | 简洁聚焦的回答，降低幻觉风险 |
| **Temperature** | 0 | 最小化幻觉；确定性输出 |
| **流式输出** | SSE (Server-Sent Events) | 用户在 1-2 秒内看到文字开始出现，而不是等 12-15 秒 |
| **查询扩展模型** | `claude-sonnet-4-20250514` | 用 Sonnet（非 Haiku）— 多语言意图映射和 Webb 专用术语识别更准确 |
| **扩展查询数** | 每个问题 3 个 | 保持低数量，避免原始问题的多语言嵌入结果被淹没 |
| **聊天历史** | 最近 6 条消息 | 支持追问，但不浪费 token |

---

## 5. 维护指南

### 5.1 年度更新清单（每年 8 月）

| 任务 | 时间 | 命令 |
|------|------|------|
| 替换 Student Handbook PDF | 新版发布时 | 复制到 `data/pdfs/`，删除旧版 |
| 替换 Course Catalog PDF | 新版发布时 | 复制到 `data/pdfs/`，删除旧版 |
| 更新 Travel Dates PDF | 新日期发布时 | 复制到 `data/pdfs/` |
| 重新抓取 webb.org | 网站内容有更新时 | `python ingest/scraper.py` |
| 重新解析 PDF | 添加/替换 PDF 后 | `python ingest/pdf_loader.py` |
| 删除旧索引 | 重建前 | `rm -rf chroma_db/` |
| 重建索引 | 数据更新后 | `python rag/build_index.py` |
| 运行测试 | 重建后 | `python tests/run_tests.py` |
| 部署 | 测试通过后 | `git push`（Render 自动部署） |

### 5.2 添加新 PDF

```bash
# 1. 将 PDF 放入 data/pdfs/
cp "新文档.pdf" data/pdfs/

# 2. 解析为 JSON
python ingest/pdf_loader.py

# 3. 重建索引（断点续传模式：只索引新文件）
python rag/build_index.py

# 4. 测试
python tests/run_tests.py

# 5. 部署
git add . && git commit -m "添加新文档" && git push
```

### 5.3 添加新网页

编辑 `ingest/scraper.py` → 在 `ALL_URLS` 列表中添加 URL，然后：

```bash
python ingest/scraper.py
python rag/build_index.py
```

### 5.4 删除过期内容

这是更困难的情况。ChromaDB 不支持按源文件轻松地部分删除。

**推荐方法：全量重建。**

```bash
# 1. 从 data/scraped/ 删除过期的 JSON 文件
rm data/scraped/pdf_old_handbook.json

# 2. 如果是 PDF，也从 data/pdfs/ 删除
rm "data/pdfs/旧版 Handbook.pdf"

# 3. 删除整个 ChromaDB 索引
rm -rf chroma_db/

# 4. 从头重建（935 个分块约需 10 分钟）
python rag/build_index.py

# 5. 验证
python tests/run_tests.py
```

**为什么要全量重建？** ChromaDB 使用 `filename_0`、`filename_1` 等格式的 ID 存储分块。逐个删除分块是可能的，但容易出错——你需要知道某个源文件的所有分块 ID。从 JSON 文件全量重建更简单，且保证一致性。

### 5.5 添加话题补充 / 关键词触发器

当发现新的跨章节政策空白（例如，关于话题 A 的问题也应该检索到章节 B 的内容），编辑 `rag/query.py`：

1. 在 `TOPIC_SUPPLEMENTS` 字典中添加新条目
2. 在 `keyword_chunks()` 的 `KEYWORD_TRIGGERS` 字典中添加新条目
3. 如果新术语需要强制包含，更新 `POLICY_CRITICAL_TERMS` 列表
4. 用相关问题测试

### 5.6 参数调优

| 如果遇到... | 尝试... | 文件 |
|------------|--------|------|
| 回答遗漏重要细节 | 增大 `CHUNK_SIZE`（如 1500） | `build_index.py` |
| 分块在句子中间截断 | 增大 `CHUNK_OVERLAP`（如 300） | `build_index.py` |
| 上下文中无关内容太多 | 减小 `MAX_CHUNKS`（如 15） | `query.py` |
| 跨章节内容缺失 | 添加到 `TOPIC_SUPPLEMENTS` | `query.py` |
| 回答质量太低 | 换生成模型（如 sonnet → opus） | `query.py` |
| 响应太慢 | 换更快的模型或减少 `MAX_CHUNKS` | `query.py` |

**重要：** 修改 `CHUNK_SIZE` 或 `CHUNK_OVERLAP` 需要全量重建索引（`rm -rf chroma_db/ && python rag/build_index.py`）。修改 `MAX_CHUNKS` 或模型则立即生效。

---

## 6. 成本估算

| 组件 | 用量 | 月成本（估算） |
|------|------|-------------|
| Gemini 嵌入 | 仅索引构建（~776 次调用） | 免费（在免费额度内） |
| Gemini 嵌入 | 查询时（~8 次/问题） | 免费 |
| Claude Sonnet（查询扩展） | 1 次/问题 | 500 个问题约 $1.50 |
| Claude Sonnet（回答生成） | 1 次/问题 | 500 个问题约 $2.00 |
| Render 托管 | 1 个 Web 服务 | 免费（750 小时/月） |
| **合计** | 500 个问题/月 | **约 $3.50/月** |

---

## 7. 文件参考

```
webb-ai/
├── ingest/
│   ├── scraper.py          # 抓取 webb.org 页面 → JSON
│   └── pdf_loader.py       # 解析 PDF → JSON
├── data/
│   ├── pdfs/               # 原始 PDF 源文件（gitignore）
│   └── scraped/            # 中间 JSON 文件（已提交）
│       ├── web_*.json      # 来自 scraper.py
│       └── pdf_*.json      # 来自 pdf_loader.py
├── rag/
│   ├── build_index.py      # JSON → 分块 → 嵌入 → ChromaDB
│   └── query.py            # 多查询检索 + Claude 生成
├── chroma_db/              # 向量数据库（已提交）
├── api/
│   └── main.py             # FastAPI 服务器
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
└── tests/
    ├── test_questions.json          # 48 道测试题
    ├── run_tests.py                 # 关键词 + LLM 评分
    ├── test_cross_language.py       # 跨语言检索一致性测试
    ├── test_results.md              # 最新结果
    └── cross_language_results.json  # 最新跨语言测试结果
```
