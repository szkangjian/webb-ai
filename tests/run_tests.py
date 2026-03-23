"""
WebbGPT automated test runner.
Reads test_questions.json, runs each through the RAG pipeline,
scores with keyword matching + LLM evaluation (Gemini 3.1 Flash-Lite),
and saves results to test_results.json and test_results.md.
"""

import json
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rag.query import answer

from google import genai
from dotenv import load_dotenv

load_dotenv(override=True)

TEST_FILE = os.path.join(os.path.dirname(__file__), "test_questions.json")
RESULT_FILE = os.path.join(os.path.dirname(__file__), "test_results.json")
MD_FILE = os.path.join(os.path.dirname(__file__), "test_results.md")

# Gemini client for LLM scoring
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
LLM_JUDGE_MODEL = "gemini-2.5-flash"  # fallback if 3.1 flash-lite unavailable


def detect_judge_model():
    """Find best available Gemini Flash model for scoring."""
    try:
        models = [m.name for m in gemini_client.models.list()]
        # Prefer newest first
        for candidate in ["gemini-2.5-flash", "gemini-2.0-flash"]:
            for m in models:
                if candidate in m:
                    print(f"  LLM Judge model: {m}")
                    return m
    except Exception:
        pass
    print(f"  LLM Judge model: {LLM_JUDGE_MODEL} (default)")
    return LLM_JUDGE_MODEL


JUDGE_PROMPT = """You are evaluating answers from a RAG-based AI chatbot for The Webb Schools (a private boarding school in Claremont, CA).

IMPORTANT: The chatbot answers questions using ONLY the context retrieved from its knowledge base (shown below). Judge accuracy based on whether the answer is FAITHFUL to this context — NOT based on your own knowledge. If the answer correctly reflects what the context says, it is accurate, even if you believe the information is outdated or different from what you know.

Retrieved context (this is what the chatbot had access to):
{context}

Question: {question}

Answer to evaluate:
{answer}

Score the answer on these 5 dimensions (1-5 each):

1. **Accuracy (faithfulness)**: Does the answer faithfully reflect the retrieved context? Are there claims NOT supported by the context? (5=fully faithful, 1=fabricates information not in context)
2. **Completeness**: Does the answer cover the key information available in the context? (5=uses context well, 1=misses important context)
3. **Relevance**: Does it stay on topic and answer what was asked? (5=perfectly relevant, 1=off-topic)
4. **Clarity**: Is it well-organized and easy to understand? (5=excellent formatting, 1=confusing)
5. **Helpfulness**: Would a student/parent find this answer useful? (5=very helpful, 1=unhelpful)

Also note any issues:
- Hallucinations: claims NOT found in the retrieved context
- Missing: important information IN the context that the answer skipped
- DO NOT penalize for information that IS in the context, even if you think it might be outdated

Respond in this exact JSON format (no markdown, no code fences):
{{"accuracy": N, "completeness": N, "relevance": N, "clarity": N, "helpfulness": N, "overall": N, "issues": "brief note or empty string"}}

where "overall" is your holistic score 1-5 (not just the average — weight accuracy and helpfulness more).
"""


def llm_score(question, answer_text, context=""):
    """Score an answer using Gemini LLM judge with retrieved context."""
    import re
    response = None
    raw_text = ""
    try:
        # Truncate context to avoid token limits (keep first 8000 chars)
        ctx = context[:8000] if context else "(no context available)"
        prompt = JUDGE_PROMPT.format(question=question, answer=answer_text, context=ctx)
        response = gemini_client.models.generate_content(
            model=judge_model,
            contents=prompt,
        )
        # Extract text from response (handle Gemini 2.5 thinking mode)
        raw_text = ""
        try:
            raw_text = response.text.strip() if response.text else ""
        except Exception:
            pass
        if not raw_text and response.candidates:
            for part in response.candidates[0].content.parts:
                if not getattr(part, 'thought', False) and part.text:
                    raw_text = part.text.strip()
                    break

        text = raw_text
        # Strip markdown code fences
        if "```" in text:
            text = text.replace("```json", "").replace("```", "").strip()
        # Find the JSON object
        match = re.search(r'\{[^{}]*\}', text)
        if match:
            text = match.group()
        scores = json.loads(text)
        # Validate required keys
        for key in ["accuracy", "completeness", "relevance", "clarity", "helpfulness", "overall"]:
            if key not in scores:
                raise ValueError(f"Missing key: {key}")
            scores[key] = int(scores[key])
        if "issues" not in scores:
            scores["issues"] = ""
        return scores
    except Exception as e:
        print(f"    ⚠️  LLM scoring failed: {e} | raw: {raw_text[:200]}")
        return None


def keyword_score(answer_text, expect_topics):
    """Original keyword-matching coverage score."""
    if not expect_topics:
        return -1, [], []
    found = []
    missing = []
    ans_lower = answer_text.lower()
    for topic in expect_topics:
        synonyms = [s.strip().lower() for s in topic.split("|")]
        if any(syn in ans_lower for syn in synonyms):
            found.append(topic)
        else:
            missing.append(topic)
    coverage = len(found) / len(expect_topics) * 100
    return round(coverage, 1), found, missing


def generate_markdown(output):
    """Generate test_results.md from results."""
    results = output["results"]
    lines = []
    lines.append("# WebbGPT Test Results")
    lines.append("")
    lines.append(f"**Test Date**: {output['test_time']}")
    lines.append(f"**Total Questions**: {output['total_questions']}")

    ok = [r for r in results if r["status"] == "ok" and r.get("coverage_pct", -1) >= 0]
    if ok:
        avg_cov = sum(r["coverage_pct"] for r in ok) / len(ok)
        lines.append(f"**Average Keyword Coverage**: {avg_cov:.1f}%")

    llm_scored = [r for r in results if r.get("llm_scores")]
    if llm_scored:
        avg_llm = sum(r["llm_scores"]["overall"] for r in llm_scored) / len(llm_scored)
        lines.append(f"**Average LLM Score**: {avg_llm:.1f}/5")

    avg_time = sum(r["time_seconds"] for r in results) / len(results)
    lines.append(f"**Average Response Time**: {avg_time:.1f}s")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Group by category
    from collections import OrderedDict
    cats = OrderedDict()
    for r in results:
        cat = r["category"]
        if cat not in cats:
            cats[cat] = []
        cats[cat].append(r)

    for cat, cat_results in cats.items():
        lines.append(f"## {cat}")
        lines.append("")

        for r in cat_results:
            cov = r.get("coverage_pct", -1)
            llm = r.get("llm_scores") or {}
            overall = llm.get("overall", 0)

            if cov < 0:
                icon = "🧪"
            elif cov >= 70 and overall >= 4:
                icon = "✅"
            elif cov >= 40 or overall >= 3:
                icon = "⚠️"
            else:
                icon = "❌"

            cov_str = f"{cov:.0f}%" if cov >= 0 else "Edge Case"
            llm_str = f"{overall}/5" if overall else "N/A"

            lines.append(f"### {icon} {r['id']}: {r['question']}")
            lines.append("")
            lines.append(f"**Keyword Coverage**: {cov_str} | **LLM Score**: {llm_str} | **Time**: {r['time_seconds']}s")

            if llm:
                lines.append(f"**Detail**: Accuracy={llm.get('accuracy','?')} Completeness={llm.get('completeness','?')} Relevance={llm.get('relevance','?')} Clarity={llm.get('clarity','?')} Helpfulness={llm.get('helpfulness','?')}")
                if llm.get("issues"):
                    lines.append(f"**Issues**: {llm['issues']}")

            if r.get("missing_topics"):
                lines.append(f"**Missing Keywords**: {', '.join(r['missing_topics'])}")
            lines.append("")
            lines.append("**Answer:**")
            lines.append("")
            lines.append(r["answer"])
            lines.append("")
            lines.append("---")
            lines.append("")

    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def run_tests():
    global judge_model
    judge_model = detect_judge_model()

    with open(TEST_FILE, encoding="utf-8") as f:
        test_data = json.load(f)

    results = []
    total = sum(len(cat["questions"]) for cat in test_data["categories"])
    current = 0

    for cat in test_data["categories"]:
        print(f"\n{'='*60}")
        print(f"  {cat['name']} ({cat['category']})")
        print(f"{'='*60}")

        for q in cat["questions"]:
            current += 1
            print(f"\n[{current}/{total}] {q['id']}: {q['question'][:50]}...")

            start = time.time()
            try:
                resp = answer(q["question"])
                elapsed = round(time.time() - start, 1)
                ans = resp["answer"]
                sources = resp["sources"]

                # Keyword scoring
                coverage, found_topics, missing_topics = keyword_score(ans, q.get("expect_topics", []))

                # LLM scoring (with retrieved context for faithful evaluation)
                llm_scores = llm_score(q["question"], ans, resp.get("context", ""))

                result = {
                    "id": q["id"],
                    "category": cat["category"],
                    "question": q["question"],
                    "language": q["language"],
                    "difficulty": q["difficulty"],
                    "answer": ans,
                    "sources": sources,
                    "time_seconds": elapsed,
                    "expect_topics": q.get("expect_topics", []),
                    "found_topics": found_topics,
                    "missing_topics": missing_topics,
                    "coverage_pct": coverage,
                    "llm_scores": llm_scores,
                    "status": "ok",
                }

                # Print summary
                cov_str = f"{coverage:.0f}%" if coverage >= 0 else "N/A"
                llm_str = ""
                if llm_scores:
                    llm_str = f" | LLM: {llm_scores['overall']}/5"
                    if llm_scores.get("issues"):
                        llm_str += f" ({llm_scores['issues'][:40]})"

                status = "✅" if (coverage >= 70 or coverage < 0) and (not llm_scores or llm_scores["overall"] >= 4) else "⚠️" if (coverage >= 40 or not llm_scores or llm_scores["overall"] >= 3) else "❌"
                print(f"  {status} Keywords: {cov_str}{llm_str} | Time: {elapsed}s")
                if missing_topics:
                    print(f"     Missing: {', '.join(missing_topics)}")

            except Exception as e:
                elapsed = round(time.time() - start, 1)
                result = {
                    "id": q["id"],
                    "category": cat["category"],
                    "question": q["question"],
                    "answer": None,
                    "time_seconds": elapsed,
                    "status": "error",
                    "error": str(e),
                }
                print(f"  ❌ ERROR: {e}")

            results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")

    ok_results = [r for r in results if r["status"] == "ok" and r.get("coverage_pct", -1) >= 0]
    llm_results = [r for r in results if r.get("llm_scores")]

    if ok_results:
        avg_coverage = sum(r["coverage_pct"] for r in ok_results) / len(ok_results)
        avg_time = sum(r["time_seconds"] for r in results) / len(results)
        high = sum(1 for r in ok_results if r["coverage_pct"] >= 70)
        mid = sum(1 for r in ok_results if 40 <= r["coverage_pct"] < 70)
        low = sum(1 for r in ok_results if r["coverage_pct"] < 40)
        errors = sum(1 for r in results if r["status"] == "error")

        print(f"Total questions: {len(results)}")
        print(f"Avg keyword coverage: {avg_coverage:.1f}%")
        if llm_results:
            avg_llm = sum(r["llm_scores"]["overall"] for r in llm_results) / len(llm_results)
            avg_acc = sum(r["llm_scores"]["accuracy"] for r in llm_results) / len(llm_results)
            avg_help = sum(r["llm_scores"]["helpfulness"] for r in llm_results) / len(llm_results)
            print(f"Avg LLM overall: {avg_llm:.1f}/5")
            print(f"Avg accuracy: {avg_acc:.1f}/5  |  Avg helpfulness: {avg_help:.1f}/5")
            low_llm = [r for r in llm_results if r["llm_scores"]["overall"] <= 2]
            if low_llm:
                print(f"Low-scoring answers:")
                for r in low_llm:
                    print(f"  - {r['id']}: {r['llm_scores']['overall']}/5 — {r['llm_scores'].get('issues','')}")
        print(f"Avg time: {avg_time:.1f}s")
        print(f"✅ Good (≥70%): {high}")
        print(f"⚠️  Medium (40-69%): {mid}")
        print(f"❌ Low (<40%): {low}")
        if errors:
            print(f"  Errors: {errors}")

    # Save results
    output = {
        "test_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_questions": len(results),
        "judge_model": judge_model,
        "results": results,
    }
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {RESULT_FILE}")

    # Generate markdown report
    generate_markdown(output)
    print(f"Report saved to: {MD_FILE}")


if __name__ == "__main__":
    run_tests()
