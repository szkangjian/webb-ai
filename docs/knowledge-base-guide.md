# WebbGPT Knowledge Base Guide

> How raw data is acquired, processed into vector embeddings, and maintained over time.

---

## 1. Architecture Overview

```
Raw Sources                 Intermediate              Vector Index
─────────────               ────────────              ────────────
webb.org (117 pages) ──►  data/scraped/*.json  ──►  ChromaDB
  via scraper.py              (plain text)          1,115 chunks
                                                    768-dim vectors
PDFs (9 files)       ──►  data/scraped/*.json  ──►  (same index)
  via pdf_loader.py           (plain text)
```

The pipeline has three stages:
1. **Acquire** — fetch raw content from websites and PDFs
2. **Process** — chunk text and generate embeddings
3. **Serve** — retrieve relevant chunks at query time

---

## 2. Data Sources

### 2.1 Website (webb.org)

| Item | Detail |
|------|--------|
| **Script** | `ingest/scraper.py` |
| **Method** | `requests` + `BeautifulSoup` (static HTML); `Playwright` for JS-rendered pages (`scrape_curriculum.py`) |
| **Source list** | Hardcoded from `webb.org/view-our-sitemap` |
| **Pages scraped** | 117 pages (69 static + 33 athletic teams + 9 additional + 6 curriculum-detail via Playwright) |
| **Output** | `data/scraped/web_*.json` |
| **Limitations** | Cannot scrape JavaScript-rendered content (AJAX team rosters, calendar events, curriculum-detail pages) |

**URL coverage by section:**

| Section | Pages | Content |
|---------|-------|---------|
| Admission | 13 | How to apply, tuition, financial aid, campus tours, FAQ |
| About | 8 | Mission, leadership, culture, news, directory |
| Academics | 13 | Core program, departments, faculty, course catalog, Alf Museum |
| Student Life | 10 | Dorm life, dining, clubs, health, weekend activities |
| Athletics | 38 | 33 individual team pages (coaches, schedules) + 5 general (CIF, records, summer practices) |
| Summer | 3 | Program tracks, brochure |
| Giving | 7 | Ways of giving, Webb Fund, endowed funds |
| Alumni | 5 | Events, awards, council |
| Other | 14 | Home, privacy, acceptances, head of school letter, college guidance profile, faculty awards, orientation, non-discrimination policy, game program |

**What is NOT captured from the website:**

| Content | Reason | Workaround |
|---------|--------|------------|
| ~~Curriculum-detail pages~~ | **Now captured** via `ingest/scrape_curriculum.py` (Playwright) | 6 departments, 143 courses, 69 faculty with emails |
| Calendar events | JavaScript-rendered (Blackbaud CMS) | Travel Dates PDFs cover key dates; chatbot redirects to webb.org/calendar |
| Athletic team rosters (student names) | JavaScript-rendered + student privacy (FERPA) | Coach names and schedules ARE captured; chatbot redirects to webb.org/athletics for rosters |
| News articles | Dynamic pages, time-sensitive content | Low Q&A value |
| Faculty detailed bios | Meet-our-faculty page only shows name/title/education (no expandable bios) | School-leadership page bios ARE captured |

### 2.2 PDF Documents

| Item | Detail |
|------|--------|
| **Script** | `ingest/pdf_loader.py` |
| **Method** | `pypdf` text extraction |
| **Source folder** | `data/pdfs/` |
| **Output** | `data/scraped/pdf_*.json` |

**Current PDF inventory:**

| PDF File | Content | Size | Year | Importance |
|----------|---------|------|------|------------|
| `2025-26 Student Handbook Final.pdf` | School policies, discipline, dorm rules, passes, honor code, daily schedule | 209,931 chars | 2025-26 | Critical |
| `course_catalog_2026-27.pdf` | All course descriptions, prerequisites, graduation requirements | 64,989 chars | 2026-27 | Critical |
| `2025-2026_college_guidance_brochure-output.pdf` | College guidance profile, SAT scores, graduation requirements, college acceptances | 4,777 chars | 2025-26 | High |
| `Travel Dates 2026-2027.pdf` | Move-in dates, breaks, departure/arrival times | 2,014 chars | 2026-27 | High |
| `Travel Dates FY26.pdf` | Same as above for current year | 1,775 chars | 2025-26 | High |
| `Device Guidelines.pdf` | Laptop specs required for new students | 1,429 chars | 2025 | Medium |
| `FAQ_TechOffice.pdf` | WiFi, printing, antivirus, tech support | 6,128 chars | 2025 | Medium |
| `WebbAUP2025.pdf` | Technology acceptable use policy | 4,682 chars | 2025 | Medium |
| `RTPWebb.pdf` | Required technology practices | 5,626 chars | 2025 | Medium |

### 2.3 External Resource Links (not indexed, provided as links)

These are referenced in responses when relevant but NOT stored in the vector index:

| Resource | URL | Trigger |
|----------|-----|---------|
| DHS: Traveling as an International Student | studyinthestates.dhs.gov/... | F-1 visa, international student travel |
| ICE: Travel Re-entry F Visa | ice.gov/sevis/travel | Visa re-entry |
| DHS: Study in the States | studyinthestates.dhs.gov | General international student info |
| DHS: Travel Reminders & Documents | studyinthestates.dhs.gov/.../travel-reminders | Travel documents |

---

## 3. Processing Pipeline

### 3.1 JSON Intermediate Format

Both scraper.py and pdf_loader.py produce the same JSON format:

```json
{
  "url": "https://www.webb.org/admission" or "local://pdf_handbook.json",
  "title": "Page or document title",
  "content": "Full text content...",
  "scraped_at": "2025-03-22T..."
}
```

All JSON files are saved to `data/scraped/`. The index builder makes no distinction between web-scraped and PDF-sourced files.

### 3.2 Text Chunking

**Script:** `rag/build_index.py` — `chunk_text()` function

**Algorithm:** Paragraph-aware chunking

```
1. Split text at paragraph boundaries (\n\n)
2. Merge consecutive small paragraphs until approaching CHUNK_SIZE
3. If a single paragraph exceeds CHUNK_SIZE, split by characters
4. Prepend CHUNK_OVERLAP characters from the previous chunk
```

**Parameters (current values):**

| Parameter | Value | Why This Value |
|-----------|-------|----------------|
| `CHUNK_SIZE` | **1,200 chars** | Large enough to preserve policy context (a full rule with its exceptions). Tested: 800 caused context fragmentation; 1,500 wasted token budget. |
| `CHUNK_OVERLAP` | **250 chars** | Prevents losing information at chunk boundaries. Critical for handbook policies where a rule and its consequence may span two paragraphs. Tested: 100 caused missed details; 400 caused excessive duplication. |

**Why paragraph-aware (not fixed-length)?**

Fixed-length splitting at character position N would cut mid-sentence, breaking the meaning of policy text. Paragraph-aware splitting respects natural section breaks in the handbook and course catalog, keeping related rules together.

**Resulting statistics:**

| Metric | Value |
|--------|-------|
| Total chunks | 935 |
| Avg chunk length | ~900 chars |
| Sources | 126 JSON documents (117 web + 9 PDF) |

### 3.3 Embedding Generation

| Parameter | Value | Why |
|-----------|-------|-----|
| **Model** | `gemini-embedding-001` | Free tier generous; native multilingual (Chinese/English/Korean/etc.); 768 dims is compact but accurate |
| **Dimensions** | 768 | Fixed by model |
| **Rate limiting** | `sleep(0.55)` between calls | Paid tier allows ~110 req/min; 0.55s keeps under limit |
| **Retry logic** | 5 retries, exponential backoff (60s, 120s, ...) | Handles 429 rate limit errors |
| **Batch size** | 10 chunks per batch | ChromaDB add() batch; does not affect embedding API (which is 1-at-a-time) |

**Why Gemini, not OpenAI?**

| Factor | Gemini embedding-001 | OpenAI text-embedding-3-large |
|--------|----------------------|-------------------------------|
| Dimensions | 768 | 3,072 |
| Quality (MTEB) | ~63 | ~64 |
| Cost | Free tier: 1,500 req/day | $0.13 per million tokens |
| Multilingual | Native | Good |
| Decision | **Selected** — quality difference negligible for 1,115 chunks; cost is zero |

### 3.4 Vector Storage (ChromaDB)

| Parameter | Value |
|-----------|-------|
| **Database** | ChromaDB (persistent, local) |
| **Distance metric** | Cosine similarity (`hnsw:space: cosine`) |
| **Collection name** | `webb_knowledge` |
| **Storage path** | `chroma_db/` |
| **Resume mode** | Checks first chunk ID per file; skips already-indexed documents |

**Why ChromaDB?**

- Zero infrastructure (no external DB server)
- Persistent to disk (survives restarts)
- 1,115 chunks fits easily in memory
- Deploys to Render free tier (34 MB on disk)

---

## 4. Retrieval Pipeline (query time)

**Script:** `rag/query.py`

### 4.1 Multi-Query Expansion

```
User Question (any language)
     │
     ├──────────────────────────────────────┐
     │                                      │
     ▼                                      ▼
Claude Sonnet → 3 English search queries    Original question (as-is)
     │                                      │
     ▼                                      ▼
Pattern match → Topic supplements (0-6)     Gemini embedding (multilingual)
     │                                      │
     ▼                                      ▼
All queries → Gemini embedding → ChromaDB   ChromaDB top-5 (+0.05 score boost)
     │                                      │
     └──────────── Merge & Deduplicate ─────┘
                         │
                         ▼
              Sort by score → Top 20 semantic chunks
                         │
                         ▼
              Keyword fallback → cross-section terms
                         │
                         ▼
              20 semantic + keyword chunks → Claude Sonnet
```

### 4.2 Cross-Language Retrieval Design

> **Key insight for future developers:** The knowledge base is in English, but users ask questions in Chinese, Korean, Japanese, Vietnamese, etc. Understanding the two-layer translation problem is critical before modifying the retrieval pipeline.

**The problem — two layers of translation loss:**

When a user asks "Webb的学费是多少？" (Chinese for "How much is Webb's tuition?"), the system must convert this into English search terms. This involves two conversion steps, each of which can lose information:

```
User: "Webb的学费是多少？"
   ↓ Layer 1: LLM translation (lossy)
expand_query() → ["Webb tuition cost", "annual fees", "boarding tuition"]
   ↓ Layer 2: Embedding (accurate)
Gemini embedding → vector search → results
```

Layer 1 (LLM translation) is where drift occurs. For example, the colloquial Chinese "周末能不能出去玩？" ("Can I go out and play on weekends?") might be translated to "weekend recreation" instead of the Webb-specific term "weekend pass".

**The solution — also search with the original question:**

Gemini's embedding model (`gemini-embedding-001`) is **natively multilingual**. It maps "学费" (Chinese) and "tuition" (English) to nearby vectors without any translation. By searching with both the original question AND the English expansions, we get:

1. **Original question search** — leverages multilingual embeddings directly, no translation loss, boosted by +0.05 score
2. **Expanded English queries** — cover different angles and Webb-specific terminology
3. **Topic supplements** — guarantee cross-section policy content

**Why 3 expanded queries (not 5):**

With 5 expansions, the original question contributes only 1/6 of search results (5 chunks out of 30). If the English translations drift, they "drown out" the original question's correct results. With 3 expansions, the original question contributes 1/4 of results, giving multilingual embeddings more weight.

**Why Sonnet for expansion (not Haiku):**

Sonnet produces significantly better English search terms from non-English input. Haiku often loses Webb-specific terminology during translation (e.g., translating "过夜假" literally instead of mapping it to "overnight pass").

**Test results (cross-language fact coverage):**

| Language | Fact Coverage | Tests |
|----------|-------------|-------|
| English | 100% | 8 |
| Chinese | 100% | 8 |
| Korean | 83% | 2 |
| Japanese | 100% | 1 |
| Vietnamese | 100% | 1 |
| **Avg en↔other chunk overlap** | **63%** | |

Test script: `tests/test_cross_language.py` — tests 8 question pairs across languages, measures key fact coverage and chunk overlap with English baseline.

### 4.3 Key Retrieval Parameters

| Parameter | Value | Why |
|-----------|-------|-----|
| `TOP_K_PER_QUERY` | **5** | Each of 4-10 queries returns 5 chunks; after dedup usually yields 15-25 unique chunks |
| `MAX_CHUNKS` | **15** | Balance between context coverage and token cost. 15 chunks × ~900 chars = ~13,500 chars, well within Sonnet's context window |
| Original query score boost | **+0.05** | Ensures chunks found via multilingual embedding (no translation loss) rank higher than translated results |
| Keyword fallback score | **0.6** (fixed) | Lower than semantic results (~0.7-0.9) so they rank below direct matches but still appear |
| Keyword snippet radius | **±200/+400 chars** | Enough to capture a full rule with its context |

### 4.4 Why We Do NOT Use Reranking

> **Warning for future developers:** Adding a reranker (e.g., Cohere Rerank, cross-encoder models) may seem like an obvious improvement, but it would likely **hurt** answer quality in this project. Read this section before making changes.

**Reranking** is a technique where, after initial retrieval, a cross-encoder model re-scores and reorders the candidate chunks to push the most relevant ones to the top.

**Why it is unnecessary here:**

1. **Small corpus** — With only 1,115 chunks, retrieval returns 20-35 candidates, and the generation model (Sonnet) reads all 20. There is no need to further narrow them down. Reranking is valuable when selecting 10 chunks from 1,000+ candidates; we don't have that problem.

2. **Multi-query already provides soft reranking** — When the same chunk is retrieved by multiple expanded queries, we keep its highest score. This naturally promotes the most broadly relevant chunks.

3. **Keyword fallback chunks would be harmed** — This is the critical risk. Our system uses keyword fallback to guarantee inclusion of cross-section policy content (e.g., CBO, extended passes, campusing). These chunks have low semantic similarity scores (fixed at 0.6) because they come from unrelated sections of the handbook. A reranker would likely score them low and push them out, **breaking the cross-section policy coverage that we worked hard to build**.

4. **Added latency** — A reranking API call adds 1-2 seconds per query, increasing an already 15s response time.

5. **Added cost and complexity** — Requires a new API key (Cohere) or model dependency, with minimal benefit for our scale.

**When to reconsider:** If the knowledge base grows to 10,000+ chunks (e.g., by adding full news archives, individual course pages, or multiple years of handbooks), retrieval quality may degrade and reranking could become valuable. At that point, ensure keyword fallback chunks are excluded from reranking (passed through directly).

### 4.5 Topic Supplements & Keyword Triggers

> **Important limitation:** These are **hardcoded** pattern-to-query mappings, NOT a general solution. They were created to fix specific cross-section retrieval failures discovered during testing — primarily the "overnight pass" question that needed to pull CBO from the discipline section. **Only 4 topics are currently covered.** Questions about other cross-referenced policies (e.g., "What accommodations are available for students with disabilities?" pulling content from both the academic and residential sections) may still miss related content.

**What they do:** When a user question matches a known topic pattern, the system injects additional search queries and scans raw documents for specific terms. This bridges gaps that pure semantic search cannot cover — for example, "overnight pass" and "Campus Beautification Opportunity" are semantically unrelated, but CBO directly affects pass eligibility.

**Current topic coverage (only 4 topics):**

| Topic Pattern | Supplemental Queries Added | Keyword Terms Searched |
|---------------|---------------------------|----------------------|
| overnight, pass, weekend leave, etc. | 6 queries (extended pass, CBO, campusing, Reach break, Community Weekends, day pass) | Campus Beautification Opportunity, extended pass, Reach break pass, campusing |
| discipline, honor, violation, etc. | 3 queries (Honor Code, probation, CBO) | Campus Beautification Opportunity, Honor Code, campusing |
| admission, apply, tuition, etc. | 3 queries (requirements, financial aid, costs) | — |
| college, university, guidance, etc. | 4 queries (counselor, a-g requirements, FAFSA, transcript) | — |

**Known gaps (topics NOT yet covered):**

- Health/medical policies cross-referencing with dorm rules
- Technology policies cross-referencing with discipline consequences
- Athletics eligibility cross-referencing with academic requirements
- Financial aid cross-referencing with enrollment conditions
- Any new cross-references introduced in future handbook editions

**How to discover new gaps:** Run the test suite (`python tests/run_tests.py`), look for low-scoring answers, and check if the missing content exists in a different section of the handbook. If so, add a new entry to `TOPIC_SUPPLEMENTS` and `KEYWORD_TRIGGERS`.

**Why hardcoding is fragile:**

1. If the handbook changes terminology (e.g., "CBO" is renamed), the triggers silently stop working
2. New cross-section relationships in future handbooks won't be caught automatically
3. Adding coverage for every possible cross-reference is impractical — the handbook has dozens of interconnected policies

**Future improvement paths:**

| Approach | How it works | Trade-off |
|----------|-------------|-----------|
| **Two-pass retrieval with LLM** | After initial retrieval, ask **Sonnet** (not Haiku): "What related policies should also be consulted for this question?" Then do a second retrieval round. Sonnet is preferred because identifying cross-section relationships requires stronger reasoning than Haiku can provide. | +1-2s latency, +$0.003/query, but automatically discovers cross-references |
| **Chunk tagging at index time** | Use an LLM (e.g., Gemini Flash) to automatically tag each chunk with topic labels (discipline, residential, academic, etc.) during indexing. **No manual labeling needed** — the LLM reads each chunk and classifies it. At query time, retrieve by topic in addition to semantic search. | One-time index rebuild (~$0.05 in LLM cost), but zero runtime cost |

### 4.6 Answer Generation

| Parameter | Value | Why |
|-----------|-------|-----|
| **Model** | `claude-sonnet-4-20250514` | Best quality-to-cost ratio; Haiku was tested but missed cross-referenced policies |
| **Max tokens** | 1,024 | Concise, focused answers reduce hallucination risk |
| **Temperature** | 0 | Minimizes hallucination; deterministic outputs |
| **Streaming** | SSE (Server-Sent Events) | User sees text appear in ~1-2s instead of waiting 12-15s |
| **Query expansion model** | `claude-sonnet-4-20250514` | Sonnet (not Haiku) — better multilingual intent mapping and Webb-specific term recognition |
| **Expanded queries** | 3 per question | Kept low so original question's multilingual embedding results aren't drowned out |
| **Chat history** | Last 6 messages | Follow-up question support without excessive token usage |

---

## 5. Maintenance Guide

### 5.1 Annual Update Checklist (every August)

| Task | When | Command |
|------|------|---------|
| Replace Student Handbook PDF | When new version is published | Copy to `data/pdfs/`, delete old version |
| Replace Course Catalog PDF | When new version is published | Copy to `data/pdfs/`, delete old version |
| Update Travel Dates PDFs | When new dates are released | Copy to `data/pdfs/` |
| Re-scrape webb.org | If website content has changed | `python ingest/scraper.py` |
| Re-parse PDFs | After adding/replacing PDFs | `python ingest/pdf_loader.py` |
| Delete old ChromaDB | Before rebuilding | `rm -rf chroma_db/` |
| Rebuild index | After all data is updated | `python rag/build_index.py` |
| Run test suite | After rebuilding | `python tests/run_tests.py` |
| Deploy | After tests pass | `git push` (auto-deploys on Render) |

### 5.2 Adding a New PDF

```bash
# 1. Place the PDF in data/pdfs/
cp "New Document.pdf" data/pdfs/

# 2. Parse it into JSON
python ingest/pdf_loader.py

# 3. Rebuild the index (resume mode: only indexes new files)
python rag/build_index.py

# 4. Test
python tests/run_tests.py

# 5. Deploy
git add . && git commit -m "Add new document" && git push
```

### 5.3 Adding a New Web Page

Edit `ingest/scraper.py` → add the URL to the `ALL_URLS` list, then:

```bash
python ingest/scraper.py
python rag/build_index.py
```

### 5.4 Removing Outdated Content

This is the harder case. ChromaDB does not support partial deletion by source file easily.

**Recommended approach: full rebuild.**

```bash
# 1. Delete the outdated JSON file from data/scraped/
rm data/scraped/pdf_old_handbook.json

# 2. If it's a PDF, also remove from data/pdfs/
rm "data/pdfs/Old Handbook.pdf"

# 3. Delete the entire ChromaDB index
rm -rf chroma_db/

# 4. Rebuild from scratch (takes ~10 minutes for 1,115 chunks)
python rag/build_index.py

# 5. Verify
python tests/run_tests.py
```

**Why full rebuild?** ChromaDB stores chunks with IDs like `filename_0`, `filename_1`, etc. Deleting individual chunks is possible but error-prone — you'd need to know all chunk IDs for a given source. A full rebuild from the JSON files is simpler and guarantees consistency.

### 5.5 Adding Topic Supplements / Keyword Triggers

When you discover a new cross-section policy gap (e.g., a question about Topic A should also retrieve content from Section B), edit `rag/query.py`:

1. Add a new entry to `TOPIC_SUPPLEMENTS` dict
2. Add a new entry to `KEYWORD_TRIGGERS` dict in `keyword_chunks()`
3. Update `POLICY_CRITICAL_TERMS` list if the new term needs forced inclusion
4. Test with a relevant question

### 5.6 Tuning Parameters

| If you see... | Try... | File |
|---------------|--------|------|
| Answers missing important details | Increase `CHUNK_SIZE` (e.g., 1500) | `build_index.py` |
| Chunks cutting mid-sentence | Increase `CHUNK_OVERLAP` (e.g., 300) | `build_index.py` |
| Too much irrelevant context | Decrease `MAX_CHUNKS` (e.g., 15) | `query.py` |
| Missing cross-section content | Add to `TOPIC_SUPPLEMENTS` | `query.py` |
| Answer quality too low | Switch generation model (e.g., claude-sonnet → opus) | `query.py` |
| Responses too slow | Switch to faster model or reduce `MAX_CHUNKS` | `query.py` |

**Important:** Changing `CHUNK_SIZE` or `CHUNK_OVERLAP` requires a full index rebuild (`rm -rf chroma_db/ && python rag/build_index.py`). Changing `MAX_CHUNKS` or models takes effect immediately.

---

## 6. Cost Estimates

| Component | Usage | Monthly Cost (est.) |
|-----------|-------|-------------------|
| Gemini Embeddings | Index build only (~776 calls) | Free (well within free tier) |
| Gemini Embeddings | Query time (~8 calls/question) | Free |
| Claude Sonnet (query expansion) | 1 call/question | ~$1.50 for 500 questions |
| Claude Sonnet (answer generation) | 1 call/question | ~$2.00 for 500 questions |
| Render hosting | 1 web service | Free (750 hrs/month) |
| **Total** | 500 questions/month | **~$3.50/month** |

---

## 7. File Reference

```
webb-ai/
├── ingest/
│   ├── scraper.py          # Fetches webb.org pages → JSON (static HTML)
│   ├── scrape_curriculum.py # Fetches curriculum-detail pages → JSON (Playwright, JS-rendered)
│   └── pdf_loader.py       # Parses PDFs → JSON
├── data/
│   ├── pdfs/               # Raw PDF source files (gitignored)
│   └── scraped/            # Intermediate JSON files (committed)
│       ├── web_*.json      # From scraper.py
│       └── pdf_*.json      # From pdf_loader.py
├── rag/
│   ├── build_index.py      # JSON → chunks → embeddings → ChromaDB
│   └── query.py            # Multi-query retrieval + Claude generation
├── chroma_db/              # Vector database (committed)
├── api/
│   └── main.py             # FastAPI server
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
└── tests/
    ├── test_questions.json       # 48 test questions
    ├── run_tests.py              # Keyword + LLM scoring
    ├── test_cross_language.py    # Cross-language retrieval consistency test
    ├── test_results.md           # Latest results
    └── cross_language_results.json  # Latest cross-language results
```
