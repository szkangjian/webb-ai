"""
Cross-language retrieval consistency test.

Tests whether asking the same question in different languages retrieves
the same chunks and produces answers of similar quality. This catches:
- Intent drift during query expansion (e.g. colloquial Chinese → wrong English search terms)
- Proper noun handling (e.g. "CBO" lost in translation)
- Numeric/date/amount corruption across languages
- Retrieval gaps unique to non-English queries

Usage:
    python tests/test_cross_language.py
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rag.query import retrieve_multi, answer, expand_query
from dotenv import load_dotenv

load_dotenv(override=True)

# Each test: same question in English and other languages
# "key_facts" are strings that MUST appear in answers regardless of language
TEST_PAIRS = [
    {
        "id": "cl-01",
        "topic": "Tuition",
        "queries": {
            "en": "How much is tuition at Webb?",
            "zh": "Webb的学费是多少？",
            "ko": "Webb 학비가 얼마인가요?",
        },
        # Use pipe-separated synonyms so Chinese/Korean answers also match
        "key_facts": ["84,070", "59,790", "financial aid|助学金|경제적 지원|奖学金"],
    },
    {
        "id": "cl-02",
        "topic": "Overnight Pass",
        "queries": {
            "en": "How many times can boarding students leave campus overnight?",
            "zh": "寄宿生每年有几次离校回家过夜的机会？",
            "ko": "기숙사 학생이 1년에 몇 번 외박할 수 있나요?",
        },
        "key_facts": ["12", "overnight|过夜|외박|离校", "pass|通行证|허가"],
    },
    {
        "id": "cl-03",
        "topic": "Fall Break",
        "queries": {
            "en": "When is fall break 2026?",
            "zh": "2026年秋假是什么时候？",
        },
        "key_facts": ["october|十月|10月", "2026"],
    },
    {
        "id": "cl-04",
        "topic": "Laptop Requirements",
        "queries": {
            "en": "What kind of laptop do I need for Webb?",
            "zh": "Webb需要什么样的电脑？",
            "vi": "Tôi cần loại laptop nào cho Webb?",
        },
        "key_facts": ["13", "i5", "8gb|8GB"],
    },
    {
        "id": "cl-05",
        "topic": "AP Courses",
        "queries": {
            "en": "Does Webb offer AP courses?",
            "zh": "Webb有AP课程吗？",
        },
        "key_facts": ["advanced studies|高级研究|高级课程", "discontinued|取消|不再提供|停止"],
    },
    {
        "id": "cl-06",
        "topic": "Colloquial Chinese",
        "queries": {
            "en": "Can I go off campus on weekends?",
            "zh": "周末能不能出去玩？",
        },
        "key_facts": ["pass|通行证|许可", "weekend|周末"],
    },
    {
        "id": "cl-07",
        "topic": "Honor Code",
        "queries": {
            "en": "What is the Honor Code at Webb?",
            "zh": "Webb的荣誉守则是什么？",
            "ja": "Webbの名誉規定は何ですか？",
        },
        "key_facts": ["honor|荣誉|名誉", "code|守则|規定|准则"],
    },
    {
        "id": "cl-08",
        "topic": "Drug Policy",
        "queries": {
            "en": "What is the drug and alcohol policy?",
            "zh": "学校对药物和酒精的政策是什么？",
        },
        "key_facts": ["drug|药物|毒品", "alcohol|酒精|酒"],
    },
]


def chunk_ids(chunks):
    """Extract comparable chunk identifiers."""
    return set(f"{c['title']}::{c['text'][:80]}" for c in chunks)


def run_tests():
    results = []
    print(f"\n{'='*70}")
    print("CROSS-LANGUAGE RETRIEVAL CONSISTENCY TEST")
    print(f"{'='*70}\n")

    for test in TEST_PAIRS:
        print(f"\n--- {test['id']}: {test['topic']} ---")

        lang_results = {}
        lang_chunks = {}
        lang_expanded = {}

        for lang, query in test["queries"].items():
            start = time.time()

            # 1. Check expanded queries
            expanded = expand_query(query)
            lang_expanded[lang] = expanded

            # 2. Retrieve chunks
            chunks = retrieve_multi(query)
            lang_chunks[lang] = chunk_ids(chunks)

            # 3. Get answer
            resp = answer(query)
            elapsed = round(time.time() - start, 1)
            ans = resp["answer"].lower()

            # 4. Check key facts (pipe-separated synonyms, e.g. "drug|药物|毒品")
            facts_found = []
            facts_missing = []
            for fact in test["key_facts"]:
                synonyms = [s.strip().lower() for s in fact.split("|")]
                if any(syn in ans for syn in synonyms):
                    facts_found.append(fact)
                else:
                    facts_missing.append(fact)

            lang_results[lang] = {
                "expanded": expanded,
                "chunk_count": len(chunks),
                "facts_found": facts_found,
                "facts_missing": facts_missing,
                "fact_coverage": len(facts_found) / len(test["key_facts"]) * 100,
                "time": elapsed,
                "answer_length": len(resp["answer"]),
            }

            status = "✅" if not facts_missing else "⚠️"
            print(f"  {lang}: {status} facts={len(facts_found)}/{len(test['key_facts'])} "
                  f"chunks={len(chunks)} time={elapsed}s"
                  f"{' missing=' + ','.join(facts_missing) if facts_missing else ''}")

        # Compare chunk overlap between English and other languages
        en_chunks = lang_chunks.get("en", set())
        for lang in test["queries"]:
            if lang == "en":
                continue
            other_chunks = lang_chunks[lang]
            overlap = len(en_chunks & other_chunks)
            total = len(en_chunks | other_chunks)
            overlap_pct = (overlap / total * 100) if total > 0 else 0
            print(f"  en↔{lang} chunk overlap: {overlap}/{total} ({overlap_pct:.0f}%)")

        results.append({
            "id": test["id"],
            "topic": test["topic"],
            "languages": lang_results,
            "en_vs_other_chunk_overlap": {
                lang: len(en_chunks & lang_chunks[lang]) / len(en_chunks | lang_chunks[lang]) * 100
                if len(en_chunks | lang_chunks[lang]) > 0 else 0
                for lang in test["queries"] if lang != "en"
            } if en_chunks else {},
        })

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    all_coverages = {}
    for r in results:
        for lang, lr in r["languages"].items():
            if lang not in all_coverages:
                all_coverages[lang] = []
            all_coverages[lang].append(lr["fact_coverage"])

    print("\nAverage fact coverage by language:")
    for lang, coverages in sorted(all_coverages.items()):
        avg = sum(coverages) / len(coverages)
        count = len(coverages)
        print(f"  {lang}: {avg:.0f}% ({count} tests)")

    all_overlaps = []
    for r in results:
        for lang, pct in r.get("en_vs_other_chunk_overlap", {}).items():
            all_overlaps.append(pct)

    if all_overlaps:
        avg_overlap = sum(all_overlaps) / len(all_overlaps)
        print(f"\nAverage en↔other chunk overlap: {avg_overlap:.0f}%")
        if avg_overlap < 50:
            print("  ⚠️  LOW OVERLAP — non-English queries retrieve significantly different chunks")
        elif avg_overlap < 70:
            print("  ⚠️  MODERATE OVERLAP — some retrieval drift across languages")
        else:
            print("  ✅  GOOD OVERLAP — consistent retrieval across languages")

    # Save results
    out_path = os.path.join(os.path.dirname(__file__), "cross_language_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "coverages": all_coverages}, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    run_tests()
