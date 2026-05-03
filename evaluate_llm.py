"""
evaluate_llm.py — Empirical evaluation of Nexus Learn LLM output quality.

PURPOSE:
    Answers the research question:
    "Can a 7B-parameter local LLM with structured prompting reliably
     generate valid, well-formed learning content across diverse topics?"

WHAT IT MEASURES:
    1. Structural completeness  — did all sections (PLAN, MCQ, CODING, MOTIVATION) generate?
    2. MCQ validity rate        — do generated questions have all options + valid answer?
    3. Plan completeness        — were all 7 days populated?
    4. Parse success rate       — did _ex() extract all expected fields?
    5. Generation time          — latency per topic
    6. Cross-topic consistency  — does quality vary between programming vs non-programming?

USAGE:
    Make sure Ollama is running: ollama serve
    Then: python evaluate_llm.py

OUTPUT:
    evaluation_results/
        raw_outputs/        — full LLM text per topic (for manual review)
        results.json        — structured metrics
        report.md           — human-readable summary for dissertation
"""

import os, sys, re, json, time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Import only LLM layer (no DB needed) ────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from llm import ask_ollama, check_ollama_status, OLLAMA_MODEL, OLLAMA_URL

try:
    from rag import retrieve_context as _retrieve_context
    _RAG_AVAILABLE = True
except Exception:
    _RAG_AVAILABLE = False
    def _retrieve_context(query, **kwargs): return ""

# ── Inline _ex() so no DB import triggered ──────────────────────
def _ex(raw, key):
    m = re.search(rf"{key}:\s*(.+?)(?=\n[A-Z_]{{2,}}:|$)", raw, re.DOTALL)
    return m.group(1).strip() if m else ""

# ════════════════════════════════════════════════════════════════
#  EVALUATION CONFIG
# ════════════════════════════════════════════════════════════════

PROGRAMMING_TOPICS = [
    "Python",
    "JavaScript",
    "Java",
    "SQL",
    "Data Structures",
]

NON_PROGRAMMING_TOPICS = [
    "Mathematics",
    "Business Management",
    "Psychology",
    "Digital Marketing",
    "Financial Planning",
]

ALL_TOPICS = PROGRAMMING_TOPICS + NON_PROGRAMMING_TOPICS

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

OUTPUT_DIR = Path("evaluation_results")
RAW_DIR    = OUTPUT_DIR / "raw_outputs"


# ════════════════════════════════════════════════════════════════
#  PROMPT BUILDER (mirrors llm.py SYSTEM_INSTRUCTION trigger)
# ════════════════════════════════════════════════════════════════

def build_eval_prompt(topic: str) -> str:
    """Sends the same message a user would type to trigger a learning package."""
    return f"I want to learn {topic}"


# ════════════════════════════════════════════════════════════════
#  PARSERS
# ════════════════════════════════════════════════════════════════

def parse_plan(raw: str) -> dict:
    """Extract weekly plan days. Returns {day: task} dict."""
    plan_block = re.search(r"PLAN_START([\s\S]*?)PLAN_END", raw)
    if not plan_block:
        return {}
    days_found = {}
    for line in plan_block.group(1).strip().split("\n"):
        m = re.match(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday):\s*(.+)$", line.strip(), re.IGNORECASE)
        if m:
            days_found[m.group(1)] = m.group(2).strip()
    return days_found


def parse_mcqs(raw: str) -> list:
    """Extract all MCQ questions. Returns list of dicts."""
    mcq_block = re.search(r"MCQ_START([\s\S]*?)MCQ_END", raw)
    if not mcq_block:
        return []
    text     = mcq_block.group(1)
    day_nums = [int(m.group(1)) for m in re.finditer(r"DAY:(\d+)", text)]
    blocks   = text.split(re.compile(r"DAY:\d+").pattern)
    mcqs     = []
    for idx, block in enumerate([b for b in re.split(r"DAY:\d+", text) if b.strip()]):
        day_num = day_nums[idx] if idx < len(day_nums) else idx + 1
        for qb in re.split(r"(?=Q:)", block.strip()):
            if not qb.strip():
                continue
            q   = re.search(r"Q:\s*(.+)", qb)
            a   = re.search(r"A\)\s*(.+)", qb)
            b   = re.search(r"B\)\s*(.+)", qb)
            c   = re.search(r"C\)\s*(.+)", qb)
            d   = re.search(r"D\)\s*(.+)", qb)
            ans = re.search(r"ANS:\s*([ABCD])", qb)
            if q and ans:
                mcqs.append({
                    "day":     day_num,
                    "question": q.group(1).strip(),
                    "has_A":   bool(a), "has_B": bool(b),
                    "has_C":   bool(c), "has_D": bool(d),
                    "answer":  ans.group(1).strip(),
                    "valid":   bool(a and b and c and d and ans),
                })
    return mcqs


def parse_coding(raw: str) -> list:
    """Extract coding tasks. Returns list of {day, task, hint}."""
    block = re.search(r"CODING_START([\s\S]*?)CODING_END", raw)
    if not block:
        return []
    text     = block.group(1)
    day_nums = [int(m.group(1)) for m in re.finditer(r"DAY:(\d+)", text)]
    tasks    = []
    for idx, seg in enumerate([s for s in re.split(r"DAY:\d+", text) if s.strip()]):
        t = re.search(r"TASK:\s*(.+)", seg)
        h = re.search(r"HINT:\s*(.+)", seg)
        if t:
            tasks.append({
                "day":  day_nums[idx] if idx < len(day_nums) else idx + 1,
                "task": t.group(1).strip(),
                "hint": h.group(1).strip() if h else "",
            })
    return tasks


def parse_motivation(raw: str) -> dict:
    """Extract motivation block fields."""
    block = re.search(r"MOTIVATION_START([\s\S]*?)MOTIVATION_END", raw)
    if not block:
        return {}
    text = block.group(1)
    return {
        "topic":     _ex(text, "TOPIC"),
        "story":     _ex(text, "STORY"),
        "daily_tip": _ex(text, "DAILY_TIP"),
    }


# ════════════════════════════════════════════════════════════════
#  METRICS
# ════════════════════════════════════════════════════════════════

def score_topic(topic: str, raw: str, elapsed: float) -> dict:
    """Run all quality checks on one LLM output. Returns metrics dict."""
    is_programming = topic in PROGRAMMING_TOPICS

    # Section presence
    has_plan     = "PLAN_START" in raw and "PLAN_END" in raw
    has_mcq      = "MCQ_START"  in raw and "MCQ_END"  in raw
    has_coding   = "CODING_START" in raw and "CODING_END" in raw
    has_motiv    = "MOTIVATION_START" in raw and "MOTIVATION_END" in raw
    has_pkg      = "LEARNING_PACKAGE_START" in raw

    # Plan quality
    plan      = parse_plan(raw)
    days_found = len(plan)
    plan_complete = days_found == 7

    # MCQ quality
    mcqs          = parse_mcqs(raw) if is_programming else []
    mcq_count     = len(mcqs)
    mcq_valid     = sum(1 for q in mcqs if q["valid"])
    mcq_valid_pct = round(mcq_valid / mcq_count * 100) if mcq_count > 0 else 0
    expected_mcqs = 21  # 3 per day × 7 days

    # Coding quality
    tasks           = parse_coding(raw) if is_programming else []
    coding_count    = len(tasks)
    coding_complete = coding_count == 7

    # Motivation quality
    motiv = parse_motivation(raw) if is_programming else {}
    motiv_complete = bool(motiv.get("story") and motiv.get("daily_tip"))

    # Overall structural score
    checks = [has_plan, plan_complete]
    if is_programming:
        checks += [has_mcq, mcq_count >= 15, has_coding, coding_complete, has_motiv, motiv_complete]
    structural_score = round(sum(checks) / len(checks) * 100)

    return {
        "topic":            topic,
        "type":             "programming" if is_programming else "non_programming",
        "elapsed_sec":      round(elapsed, 1),
        "has_package":      has_pkg,
        "has_plan":         has_plan,
        "plan_days_found":  days_found,
        "plan_complete":    plan_complete,
        "has_mcq":          has_mcq,
        "mcq_count":        mcq_count,
        "mcq_valid":        mcq_valid,
        "mcq_valid_pct":    mcq_valid_pct,
        "expected_mcqs":    expected_mcqs if is_programming else 0,
        "has_coding":       has_coding,
        "coding_count":     coding_count,
        "coding_complete":  coding_complete,
        "has_motivation":   has_motiv,
        "motivation_complete": motiv_complete,
        "structural_score": structural_score,
        "plan_days":        plan,
    }


# ════════════════════════════════════════════════════════════════
#  REPORT GENERATOR
# ════════════════════════════════════════════════════════════════

def generate_report(results: list, model: str, run_at: str) -> str:
    total     = len(results)
    prog      = [r for r in results if r["type"] == "programming"]
    non_prog  = [r for r in results if r["type"] == "non_programming"]

    avg_struct  = round(sum(r["structural_score"] for r in results) / total)
    avg_time    = round(sum(r["elapsed_sec"] for r in results) / total, 1)
    plan_ok     = sum(1 for r in results if r["plan_complete"])
    pkg_ok      = sum(1 for r in results if r["has_package"])

    # MCQ stats (programming only)
    total_mcqs  = sum(r["mcq_count"] for r in prog)
    valid_mcqs  = sum(r["mcq_valid"] for r in prog)
    mcq_pct     = round(valid_mcqs / total_mcqs * 100) if total_mcqs > 0 else 0

    lines = [
        f"# Nexus Learn — LLM Output Quality Evaluation",
        f"",
        f"**Model:** `{model}`  ",
        f"**Run date:** {run_at}  ",
        f"**Topics tested:** {total} ({len(prog)} programming, {len(non_prog)} non-programming)  ",
        f"",
        f"---",
        f"",
        f"## Summary Metrics",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Overall structural completeness | **{avg_struct}%** |",
        f"| Learning packages generated correctly | {pkg_ok}/{total} |",
        f"| Weekly plans fully populated (7/7 days) | {plan_ok}/{total} |",
        f"| MCQ questions generated (programming topics) | {total_mcqs} |",
        f"| MCQs with valid format (4 options + answer) | {valid_mcqs} ({mcq_pct}%) |",
        f"| Average generation time per topic | {avg_time}s |",
        f"",
        f"---",
        f"",
        f"## Per-Topic Results",
        f"",
        f"| Topic | Type | Struct% | Plan Days | MCQs | Valid MCQs | Coding | Time(s) |",
        f"|-------|------|---------|-----------|------|------------|--------|---------|",
    ]

    for r in results:
        mcq_str  = str(r["mcq_count"])  if r["type"] == "programming" else "N/A"
        vld_str  = f"{r['mcq_valid_pct']}%" if r["type"] == "programming" else "N/A"
        code_str = "✅" if r["coding_complete"] else (str(r["coding_count"]) if r["has_coding"] else "❌")
        plan_str = f"{r['plan_days_found']}/7 {'✅' if r['plan_complete'] else '⚠️'}"
        lines.append(
            f"| {r['topic']} | {r['type'][:4]} | {r['structural_score']}% "
            f"| {plan_str} | {mcq_str} | {vld_str} | {code_str} | {r['elapsed_sec']}s |"
        )

    lines += [
        f"",
        f"---",
        f"",
        f"## Programming vs Non-Programming Quality",
        f"",
        f"| Category | Avg Structural Score | Avg Plan Completeness |",
        f"|----------|---------------------|-----------------------|",
    ]

    def avg(lst, key): return round(sum(r[key] for r in lst) / len(lst)) if lst else 0

    lines += [
        f"| Programming | {avg(prog, 'structural_score')}% | {avg(prog, 'plan_days_found')}/7 days |",
        f"| Non-Programming | {avg(non_prog, 'structural_score')}% | {avg(non_prog, 'plan_days_found')}/7 days |",
        f"",
        f"---",
        f"",
        f"## Key Findings",
        f"",
        f"- The model generated valid weekly plans for **{plan_ok}/{total}** topics.",
        f"- Of {total_mcqs} MCQ questions generated, **{valid_mcqs} ({mcq_pct}%)** had correct structure (4 options + valid answer letter).",
        f"- Average response latency was **{avg_time}s** per topic on `{model}`.",
        f"- Raw LLM outputs saved in `evaluation_results/raw_outputs/` for manual factual review.",
        f"",
        f"## Manual Review Required",
        f"",
        f"The automated evaluation above checks **structural validity** only.",
        f"For **factual accuracy**, manually review the MCQ questions in `raw_outputs/`",
        f"and complete `evaluation_results/manual_grading.csv`.",
        f"",
        f"Suggested sample: grade 5 MCQs per topic = {len(prog) * 5} questions total.",
    ]

    return "\n".join(lines)


def generate_manual_grading_csv(results: list) -> str:
    """CSV template for manual factual grading of MCQs."""
    rows = ["topic,day,question,answer,factually_correct(Y/N),distractor_quality(1-3),notes"]
    for r in results:
        if r["type"] != "programming":
            continue
        topic = r["topic"]
        raw_path = RAW_DIR / f"{topic.replace(' ','_')}.txt"
        if not raw_path.exists():
            continue
        raw  = raw_path.read_text(encoding="utf-8")
        mcqs = parse_mcqs(raw)
        for q in mcqs[:3]:  # first 3 per topic as sample
            question_escaped = q["question"].replace(",", ";")
            rows.append(f'{topic},{q["day"]},"{question_escaped}",{q["answer"]},,, ')
    return "\n".join(rows)


# ════════════════════════════════════════════════════════════════
#  RAG COMPARISON
# ════════════════════════════════════════════════════════════════

RAG_TEST_QUESTIONS = [
    {
        "question": "What is a binary search tree and how does insertion work?",
        "keywords": ["binary", "search", "tree", "node", "left", "right", "insert", "compare"],
    },
    {
        "question": "Explain the difference between TCP and UDP protocols.",
        "keywords": ["tcp", "udp", "reliable", "connection", "packet", "handshake", "stateless"],
    },
    {
        "question": "What is the time complexity of quicksort and when does worst case occur?",
        "keywords": ["quicksort", "O(n log n)", "pivot", "worst", "O(n^2)", "partition"],
    },
    {
        "question": "How does garbage collection work in Python?",
        "keywords": ["garbage", "collection", "reference", "count", "cyclic", "memory", "GC"],
    },
    {
        "question": "What is normalisation in relational databases and why is it important?",
        "keywords": ["normalisation", "1NF", "2NF", "3NF", "redundancy", "dependency", "relation"],
    },
]


def _keyword_overlap(response: str, keywords: list) -> float:
    """Fraction of expected keywords found (case-insensitive) in the response."""
    text = response.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text)
    return round(hits / len(keywords), 3) if keywords else 0.0


def run_rag_comparison() -> dict:
    """
    Ask 5 CS questions with and without RAG context.
    Measures response length and keyword overlap with expected answers.
    Returns a summary dict and writes evaluation_results/rag_comparison.json.
    """
    print("\n" + "=" * 60)
    print("  RAG Comparison Evaluation")
    print("=" * 60)

    if not _RAG_AVAILABLE:
        print("⚠️  RAG not available (ChromaDB/sentence-transformers missing). Skipping.")
        return {}

    OUTPUT_DIR.mkdir(exist_ok=True)

    comparisons = []

    for i, item in enumerate(RAG_TEST_QUESTIONS, 1):
        q        = item["question"]
        keywords = item["keywords"]
        print(f"\n[{i}/5] {q[:60]}...")

        # Without RAG
        t0 = time.time()
        try:
            resp_no_rag = ask_ollama([], q)
        except Exception as e:
            resp_no_rag = f"ERROR: {e}"
        time_no_rag = round(time.time() - t0, 1)

        # With RAG — retrieve context then build augmented prompt
        rag_ctx = _retrieve_context(q)
        rag_prompt = q
        if rag_ctx:
            rag_prompt = f"[Context]\n{rag_ctx}\n\n[Question]\n{q}"
        t0 = time.time()
        try:
            resp_with_rag = ask_ollama([], rag_prompt)
        except Exception as e:
            resp_with_rag = f"ERROR: {e}"
        time_with_rag = round(time.time() - t0, 1)

        len_no_rag   = len(resp_no_rag.split())
        len_with_rag = len(resp_with_rag.split())
        kw_no_rag    = _keyword_overlap(resp_no_rag, keywords)
        kw_with_rag  = _keyword_overlap(resp_with_rag, keywords)

        comparisons.append({
            "question":         q,
            "keywords":         keywords,
            "no_rag": {
                "response_words":   len_no_rag,
                "keyword_overlap":  kw_no_rag,
                "elapsed_sec":      time_no_rag,
            },
            "with_rag": {
                "rag_context_found": bool(rag_ctx),
                "response_words":    len_with_rag,
                "keyword_overlap":   kw_with_rag,
                "elapsed_sec":       time_with_rag,
            },
            "keyword_improvement": round(kw_with_rag - kw_no_rag, 3),
            "length_delta_words":  len_with_rag - len_no_rag,
        })

        print(f"    No RAG  → {len_no_rag:4d} words | kw overlap {kw_no_rag:.0%}")
        print(f"    With RAG → {len_with_rag:4d} words | kw overlap {kw_with_rag:.0%} | ctx={'yes' if rag_ctx else 'none'}")

    # Aggregate
    avg_kw_improvement = round(
        sum(c["keyword_improvement"] for c in comparisons) / len(comparisons) * 100, 1
    ) if comparisons else 0.0
    avg_len_delta = round(
        sum(c["length_delta_words"] for c in comparisons) / len(comparisons), 1
    ) if comparisons else 0.0

    summary = {
        "model":               OLLAMA_MODEL,
        "run_at":              datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "rag_available":       _RAG_AVAILABLE,
        "questions_tested":    len(comparisons),
        "avg_keyword_improvement_pct": avg_kw_improvement,
        "avg_response_length_delta_words": avg_len_delta,
        "comparisons":         comparisons,
    }

    out_path = OUTPUT_DIR / "rag_comparison.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\n{'─'*60}")
    print(f"  RAG Improvement Summary")
    print(f"{'─'*60}")
    print(f"  Avg keyword overlap improvement : {avg_kw_improvement:+.1f}%")
    print(f"  Avg response length delta       : {avg_len_delta:+.1f} words")
    print(f"  Results saved → {out_path}")

    return summary


# ════════════════════════════════════════════════════════════════
#  MAIN RUNNER
# ════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  Nexus Learn — LLM Evaluation")
    print("=" * 60)

    # Check Ollama running
    status = check_ollama_status()
    if not status["ok"]:
        print(f"\n❌  Ollama not running. Start with: ollama serve")
        sys.exit(1)
    print(f"\n✅  Ollama running | Model: {OLLAMA_MODEL}")
    print(f"    URL: {OLLAMA_URL}")

    # Setup output dirs
    OUTPUT_DIR.mkdir(exist_ok=True)
    RAW_DIR.mkdir(exist_ok=True)

    results  = []
    run_at   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print(f"\nEvaluating {len(ALL_TOPICS)} topics...\n")

    for i, topic in enumerate(ALL_TOPICS, 1):
        print(f"[{i:02d}/{len(ALL_TOPICS)}] {topic:<25}", end="", flush=True)

        prompt  = build_eval_prompt(topic)
        t_start = time.time()

        try:
            raw     = ask_ollama([], prompt)
            elapsed = time.time() - t_start

            # Save raw output
            raw_file = RAW_DIR / f"{topic.replace(' ','_')}.txt"
            raw_file.write_text(raw, encoding="utf-8")

            metrics = score_topic(topic, raw, elapsed)
            results.append(metrics)

            status_icon = "✅" if metrics["structural_score"] >= 70 else "⚠️"
            print(f" {status_icon}  {metrics['structural_score']:3d}% struct | "
                  f"{metrics['plan_days_found']}/7 days | "
                  f"{metrics['mcq_count']:2d} MCQs | {elapsed:.1f}s")

        except Exception as e:
            elapsed = time.time() - t_start
            print(f" ❌  ERROR: {e}")
            results.append({
                "topic": topic, "type": "programming" if topic in PROGRAMMING_TOPICS else "non_programming",
                "elapsed_sec": round(elapsed, 1), "error": str(e),
                "structural_score": 0, "plan_days_found": 0, "plan_complete": False,
                "has_package": False, "has_plan": False, "has_mcq": False,
                "mcq_count": 0, "mcq_valid": 0, "mcq_valid_pct": 0, "expected_mcqs": 0,
                "has_coding": False, "coding_count": 0, "coding_complete": False,
                "has_motivation": False, "motivation_complete": False, "plan_days": {},
            })

    # Save JSON results
    json_path = OUTPUT_DIR / "results.json"
    json_path.write_text(
        json.dumps({"model": OLLAMA_MODEL, "run_at": run_at, "results": results}, indent=2),
        encoding="utf-8"
    )

    # Save markdown report
    report     = generate_report(results, OLLAMA_MODEL, run_at)
    report_path = OUTPUT_DIR / "report.md"
    report_path.write_text(report, encoding="utf-8")

    # Save manual grading CSV
    csv       = generate_manual_grading_csv(results)
    csv_path  = OUTPUT_DIR / "manual_grading.csv"
    csv_path.write_text(csv, encoding="utf-8")

    # Print summary
    valid = [r for r in results if "error" not in r]
    avg_s = round(sum(r["structural_score"] for r in valid) / len(valid)) if valid else 0
    print(f"\n{'='*60}")
    print(f"  DONE — {len(valid)}/{len(ALL_TOPICS)} topics succeeded")
    print(f"  Average structural score: {avg_s}%")
    print(f"{'='*60}")
    print(f"\n📁 Results saved:")
    print(f"   {report_path}          ← paste into dissertation")
    print(f"   {json_path}            ← full data")
    print(f"   {csv_path}  ← manually grade MCQs here")
    print(f"   {RAW_DIR}/              ← raw LLM outputs\n")

    run_rag_comparison()


if __name__ == "__main__":
    main()