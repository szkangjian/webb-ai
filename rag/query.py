"""
RAG query engine with Multi-Query expansion.
Embeddings: Gemini gemini-embedding-001 (free, native multilingual)
Generation: Claude claude-sonnet-4-20250514 via Anthropic API (Haiku for query expansion)
"""

import os
import chromadb
import anthropic
from google import genai
from dotenv import load_dotenv

load_dotenv(override=True)

gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
COLLECTION_NAME = "webb_knowledge"
EMBED_MODEL = "gemini-embedding-001"
TOP_K_PER_QUERY = 5   # chunks per expanded query
MAX_CHUNKS = 15        # max total chunks after dedup (lower = less noise = less hallucination)

SYSTEM_PROMPT = """You are a document reader for The Webb Schools.

## CRITICAL: You know NOTHING about Webb Schools.

Pretend you have never heard of Webb Schools before. You are reading these documents for the very first time. The ONLY information you have is what appears inside the <context> tags in the user message.

## Rules

1. EVERY fact you state MUST come from a specific sentence in <context>. If you cannot quote or closely paraphrase a sentence from <context>, do NOT include that fact.

2. NEVER add information from outside <context>, even if you believe it is correct. Common mistakes to avoid:
   - Adding sports, clubs, courses, or programs not listed in <context>
   - Adding numbers, statistics, or counts not stated in <context>
   - Adding staff names, emails, addresses, or phone numbers not in <context>
   - Adding policy details, rules, or consequences not in <context>
   - Adding URLs not in <context> (only webb.org, webb.org/athletics, webb.org/calendar are allowed)
   - Saying "there are X total" when <context> doesn't state the total

3. When <context> is incomplete, say: "The documents I have access to show [what you found]. For additional information, please contact the school or visit webb.org."

4. A SHORT, ACCURATE answer is always better than a LONG answer with added details.

## Format
- Use bullet points and bold for key terms
- Sources marked [RELATED POLICY] must be fully covered
- Respond in the same language as the question
- For health/safety emergencies → contact school staff
- For athletic rosters/schedules → webb.org/athletics
- For calendar/events → webb.org/calendar"""


def expand_query(question):
    """
    Use Claude Sonnet to generate 3 English search queries from the user's question.
    Kept to 3 (not 5) so the original question's multilingual embedding results
    aren't drowned out by translated queries.
    """
    response = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=256,
        system="""You generate search queries for The Webb Schools knowledge base.
Webb Schools uses these specific terms in their documents:
- Overnight Pass / Weekend Pass: permission to leave campus overnight
- Extended Pass: special pass for longer or unusual circumstances
- Community Weekends: mandatory on-campus weekends, no passes allowed
- CBO (Campus Beautification Obligation): penalty task that blocks pass usage
- Campus Restriction: disciplinary measure blocking passes
- Reach break pass: permission form for vacation/break periods
- Dorm Head: dormitory supervisor who approves passes
- Day student / Boarding student: day vs residential students

Output ONLY a JSON array of 3 short English search phrases covering different aspects of the question, including relevant Webb-specific terms where applicable. No explanation.""",
        messages=[{"role": "user", "content": f"Question: {question}"}],
    )
    text = response.content[0].text.strip()
    # Parse JSON array
    import json, re
    match = re.search(r'\[.*?\]', text, re.DOTALL)
    if match:
        try:
            queries = json.loads(match.group())
            return [q.strip() for q in queries if isinstance(q, str)][:3]
        except Exception:
            pass
    # Fallback: return original question
    return [question]


def get_embedding(text):
    """Get embedding using Gemini - natively handles any language."""
    result = gemini.models.embed_content(
        model=EMBED_MODEL,
        contents=text,
    )
    return result.embeddings[0].values


# Topic-specific supplemental queries: when a question is about one of these topics,
# always add the related Webb-specific terms to ensure full policy coverage.
TOPIC_SUPPLEMENTS = {
    "overnight|pass|weekend leave|离校|过夜|回家|寄宿": [
        "extended pass special events family occasions dorm head Wednesday",
        "CBO Campus Beautification Opportunity consequence unexcused absence discipline weekend",
        "campus restriction campusing off-campus privileges revoked",
        "Reach break pass vacation period sign out",
        "Community Weekends mandatory on campus no passes allowed",
        "six-hour day pass weekend off campus",
    ],
    "discipline|honor|violation|纪律|违规|荣誉": [
        "Honor Code violation consequences Webb",
        "disciplinary probation suspension expulsion",
        "CBO Campus Beautification Obligation penalty",
    ],
    "admission|apply|tuition|financial aid|申请|录取|学费": [
        "Webb Schools application requirements deadlines",
        "financial aid scholarship eligibility",
        "tuition fees boarding day student cost",
    ],
    "college|university|guidance|counselor|大学|升学|辅导": [
        "college guidance counselor Webb Schools",
        "a-g requirements college admission",
        "FAFSA financial aid college application",
        "transcript recommendation letter process",
    ],
}


def get_supplemental_queries(question):
    """Return topic-specific supplemental queries based on question content."""
    import re
    question_lower = question.lower()
    supplements = []
    for pattern, queries in TOPIC_SUPPLEMENTS.items():
        if re.search(pattern, question_lower):
            supplements.extend(queries)
    return supplements


def keyword_chunks(question, data_dir=None):
    """
    Keyword fallback: scan raw documents for Webb-specific terms mentioned
    or implied by the question topic, and return matching text snippets.
    Bridges cross-section gaps that semantic search cannot cover.
    """
    import re, json, os
    if data_dir is None:
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "scraped")

    question_lower = question.lower()

    # Map: trigger pattern → terms to search in documents
    KEYWORD_TRIGGERS = {
        r"overnight|pass|weekend leave|离校|过夜|回家|寄宿": [
            "Campus Beautification Opportunity",
            "extended pass",
            "Reach break pass",
            "campusing",
        ],
        r"discipline|honor|violation|纪律|违规": [
            "Campus Beautification Opportunity",
            "Honor Code",
            "campusing",
        ],
    }

    snippets = []
    for pattern, keywords in KEYWORD_TRIGGERS.items():
        if not re.search(pattern, question_lower):
            continue
        # Search all scraped/PDF files
        for fname in os.listdir(data_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(data_dir, fname)
            with open(fpath, encoding="utf-8") as f:
                doc = json.load(f)
            content = doc.get("content", "")
            source = doc.get("url", f"local://{fname}")
            title = doc.get("title", fname)
            for kw in keywords:
                idx = content.lower().find(kw.lower())
                if idx >= 0:
                    # Extract ±400 chars around the keyword
                    start = max(0, idx - 200)
                    end = min(len(content), idx + 400)
                    snippet_text = content[start:end].strip()
                    snippets.append({
                        "text": snippet_text,
                        "source": source,
                        "title": title,
                        "score": 0.6,  # Fixed score, lower than semantic results
                    })
    return snippets


def retrieve_multi(question, top_k_per_query=TOP_K_PER_QUERY, max_chunks=MAX_CHUNKS):
    """
    Multi-query retrieval:
    1. Expand the question into multiple search queries
    2. Add topic-specific supplemental queries for known Webb policy areas
    3. Retrieve chunks for each query
    4. Deduplicate and rank by best score
    """
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = chroma_client.get_collection(COLLECTION_NAME)

    # Original + LLM-expanded + topic supplements
    expanded = expand_query(question)
    queries = [question] + expanded + get_supplemental_queries(question)
    # Keyword fallback chunks (cross-section content like CBO)
    keyword_results = keyword_chunks(question)

    seen_texts = {}  # text → best chunk dict

    for i, query in enumerate(queries):
        is_original = (i == 0)  # first query is the user's original question
        embedding = get_embedding(query)
        results = collection.query(
            query_embeddings=[embedding],
            n_results=top_k_per_query,
            include=["documents", "metadatas", "distances"],
        )
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            score = round(1 - dist, 3)
            # Boost original question results: the multilingual embedding
            # directly captures user intent without translation loss
            if is_original:
                score = min(round(score + 0.05, 3), 1.0)
            # Keep the highest score if this chunk appears in multiple queries
            if doc not in seen_texts or seen_texts[doc]["score"] < score:
                seen_texts[doc] = {
                    "text": doc,
                    "source": meta["source"],
                    "title": meta["title"],
                    "score": score,
                }

    # Sort semantic chunks by score, take top max_chunks
    semantic_chunks = sorted(seen_texts.values(), key=lambda x: x["score"], reverse=True)[:max_chunks]

    # Always append keyword chunks — deduplicate by checking if the
    # KEYWORD TERM itself already appears in any semantic chunk (not just prefix match)
    semantic_text_combined = " ".join(c["text"].lower() for c in semantic_chunks)
    guaranteed = []
    for kchunk in keyword_results:
        # Find the keyword that triggered this chunk
        kw_found_in_semantic = False
        for kw in ["campus beautification opportunity", "extended pass", "reach break", "campusing"]:
            if kw in kchunk["text"].lower() and kw in semantic_text_combined:
                kw_found_in_semantic = True
                break
        if not kw_found_in_semantic:
            guaranteed.append(kchunk)

    return semantic_chunks + guaranteed


def _intl_student_note(question):
    """Return external resource links if the question is about international students."""
    q_lower = question.lower()
    if any(kw in q_lower for kw in [
        "international student", "f-1", "f1 visa", "i-20", "i20", "sevis",
        "travel re-entry", "visa", "国际生", "签证", "留学生", "入境",
    ]):
        return (
            "\n\nAdditional resources for international students (include these links in your answer when relevant):\n"
            "- Traveling as an International Student: https://studyinthestates.dhs.gov/students/study/traveling-as-an-international-student\n"
            "- Travel Re-entry F Visa: https://www.ice.gov/sevis/travel\n"
            "- Study in the States (DHS): https://studyinthestates.dhs.gov/\n"
            "- Travel Reminders & Documents: https://studyinthestates.dhs.gov/students/study/travel-reminders-and-documents\n"
        )
    return ""


def answer(question, chat_history=None):
    """
    Generate an answer using multi-query retrieved context.

    Args:
        question: The user's question (any language).
        chat_history: Optional list of {"role": "user"/"assistant", "content": "..."} dicts.

    Returns:
        dict with "answer" string and "sources" list.
    """
    chunks = retrieve_multi(question)

    # Terms that signal a chunk contains must-include policy content
    POLICY_CRITICAL_TERMS = [
        "extended pass", "campus beautification", "campusing", "campus restriction",
        "reach break", "community weekend", "honor code violation",
        "disciplinary probation", "suspension", "expulsion",
    ]

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        chunk_lower = chunk["text"].lower()
        # Mark as RELATED POLICY if: keyword fallback chunk OR contains critical policy terms
        is_policy = chunk.get("score") == 0.6 or any(
            t in chunk_lower for t in POLICY_CRITICAL_TERMS
        )
        label = f"[Source {i}: {chunk['title']}]"
        if is_policy:
            label = f"[Source {i} - RELATED POLICY, must include in answer: {chunk['title']}]"
        context_parts.append(f"{label}\n{chunk['text']}")
    context = "\n\n---\n\n".join(context_parts)

    messages = []
    if chat_history:
        messages.extend(chat_history[-6:])

    # Check if we have any RELATED POLICY chunks
    has_related_policy = any(
        chunk.get("score") == 0.6 or any(
            t in chunk["text"].lower() for t in POLICY_CRITICAL_TERMS
        )
        for chunk in chunks
    )
    # Build list of key terms found in RELATED POLICY chunks for explicit callout
    policy_terms_found = set()
    term_labels = {
        "extended pass": "Extended Pass (special events/family occasions from dorm head)",
        "campus beautification": "CBO / Campus Beautification Opportunity (blocks pass eligibility)",
        "campusing": "Campus Restriction / Campusing (revokes off-campus privileges)",
        "reach break": "Reach Break Pass (vacation/break sign-out)",
        "community weekend": "Community Weekends (no passes allowed)",
    }
    for chunk in chunks:
        chunk_lower = chunk["text"].lower()
        for term, label in term_labels.items():
            if term in chunk_lower:
                policy_terms_found.add(label)

    if has_related_policy and policy_terms_found:
        terms_list = "\n".join(f"  - {t}" for t in sorted(policy_terms_found))
        policy_note = (
            f"\n\nCRITICAL INSTRUCTION: The context contains [RELATED POLICY] sources. "
            f"Your answer MUST explicitly mention ALL of the following policies found in the context "
            f"(do not skip any of them):\n{terms_list}\n"
            f"Integrate each one into your answer with a clear explanation."
        )
    elif has_related_policy:
        policy_note = (
            "\n\nNOTE: This context includes sources marked [RELATED POLICY]. "
            "You MUST explicitly include ALL content from those sources in your answer."
        )
    else:
        policy_note = ""

    user_content = (
        f"<context>\n{context}\n</context>\n\n"
        f"Question: {question}{policy_note}{_intl_student_note(question)}"
    )
    messages.append({"role": "user", "content": user_content})

    sources = []
    seen_sources = set()
    for c in chunks:
        src = c["source"]
        if src.startswith("local://"):
            label = c.get("title", src.replace("local://", ""))
        else:
            label = src
        if label not in seen_sources:
            seen_sources.add(label)
            sources.append(label)

    response = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    return {
        "answer": response.content[0].text,
        "sources": sources,
        "context": context,
    }


def answer_stream(question, chat_history=None):
    """
    Streaming version of answer(). Yields:
      - {"type": "sources", "sources": [...]}  (first, before text)
      - {"type": "delta", "text": "..."}       (incremental text chunks)
      - {"type": "done"}                       (stream finished)
    """
    chunks = retrieve_multi(question)

    POLICY_CRITICAL_TERMS = [
        "extended pass", "campus beautification", "campusing", "campus restriction",
        "reach break", "community weekend", "honor code violation",
        "disciplinary probation", "suspension", "expulsion",
    ]

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        chunk_lower = chunk["text"].lower()
        is_policy = chunk.get("score") == 0.6 or any(
            t in chunk_lower for t in POLICY_CRITICAL_TERMS
        )
        label = f"[Source {i}: {chunk['title']}]"
        if is_policy:
            label = f"[Source {i} - RELATED POLICY, must include in answer: {chunk['title']}]"
        context_parts.append(f"{label}\n{chunk['text']}")
    context = "\n\n---\n\n".join(context_parts)

    messages = []
    if chat_history:
        messages.extend(chat_history[-6:])

    has_related_policy = any(
        chunk.get("score") == 0.6 or any(
            t in chunk["text"].lower() for t in POLICY_CRITICAL_TERMS
        )
        for chunk in chunks
    )

    term_labels = {
        "extended pass": "Extended Pass (special events/family occasions from dorm head)",
        "campus beautification": "CBO / Campus Beautification Opportunity (blocks pass eligibility)",
        "campusing": "Campus Restriction / Campusing (revokes off-campus privileges)",
        "reach break": "Reach Break Pass (vacation/break sign-out)",
        "community weekend": "Community Weekends (no passes allowed)",
    }
    policy_terms_found = set()
    for chunk in chunks:
        chunk_lower = chunk["text"].lower()
        for term, label in term_labels.items():
            if term in chunk_lower:
                policy_terms_found.add(label)

    if has_related_policy and policy_terms_found:
        terms_list = "\n".join(f"  - {t}" for t in sorted(policy_terms_found))
        policy_note = (
            f"\n\nCRITICAL INSTRUCTION: The context contains [RELATED POLICY] sources. "
            f"Your answer MUST explicitly mention ALL of the following policies found in the context "
            f"(do not skip any of them):\n{terms_list}\n"
            f"Integrate each one into your answer with a clear explanation."
        )
    elif has_related_policy:
        policy_note = (
            "\n\nNOTE: This context includes sources marked [RELATED POLICY]. "
            "You MUST explicitly include ALL content from those sources in your answer."
        )
    else:
        policy_note = ""

    user_content = (
        f"<context>\n{context}\n</context>\n\n"
        f"Question: {question}{policy_note}{_intl_student_note(question)}"
    )
    messages.append({"role": "user", "content": user_content})

    # Yield sources first so frontend can display them early
    sources = []
    seen_sources = set()
    for c in chunks:
        src = c["source"]
        if src.startswith("local://"):
            label = c.get("title", src.replace("local://", ""))
        else:
            label = src
        if label not in seen_sources:
            seen_sources.add(label)
            sources.append(label)

    yield {"type": "sources", "sources": sources}

    # Stream the response
    with claude.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield {"type": "delta", "text": text}

    yield {"type": "done"}


if __name__ == "__main__":
    q = "寄宿生每年有几次离校回家过夜的机会"
    print(f"Q: {q}\n")
    result = answer(q)
    print(f"A: {result['answer']}\n")
    print(f"Sources: {result['sources']}")
