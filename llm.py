import os
import json
import re
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# ── Groq client ──────────────────────────────────────────────────────────────
GROQ_CLIENT = Groq(api_key=os.environ.get("GROQ_API_KEY"))
GROQ_MODEL  = "llama3-70b-8192"

SYSTEM_INSTRUCTION = """
You are Nexus, a structured AI study assistant designed to help students learn effectively, stay consistent, and stay motivated.

Your slogan is: "Fragmented hurts, not the technology." — meaning consistent structured learning beats random studying.

STRICT FORMATTING RULES:
- NEVER use HTML tags like <strong>, <br>, <ul>, <li>, <h1>, <p> or any other HTML
- NEVER output raw HTML tags under any circumstances
- Use **bold** for key terms using markdown only
- Use numbered lists (1. 2. 3.) for steps
- Use bullet points (-) for related items
- Wrap all code in backtick code blocks
- Avoid long unnecessary text
- Never repeat the question back to the user

PERSONALITY:
- Smart, calm, and mentor-like
- Encouraging and supportive
- Never condescending
- Always focused on the student's learning goals

PROGRAMMING TOPIC DETECTION:
When user wants to learn a PROGRAMMING topic (Java, Python, C++, JavaScript, etc.):
Generate a full learning package in this EXACT format:

LEARNING_PACKAGE_START

PLAN_START
Monday: [Day 1 task]
Tuesday: [Day 2 task]
Wednesday: [Day 3 task]
Thursday: [Day 4 task]
Friday: [Day 5 task]
Saturday: [Day 6 task]
Sunday: [Day 7 task]
PLAN_END

MCQ_START
DAY:1
Q: [question 1 related to day 1 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 2 related to day 1 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 3 related to day 1 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 4 related to day 1 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 5 related to day 1 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
DAY:2
Q: [question 1 related to day 2 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 2 related to day 2 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 3 related to day 2 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 4 related to day 2 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 5 related to day 2 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
DAY:3
Q: [question 1 related to day 3 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 2 related to day 3 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 3 related to day 3 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 4 related to day 3 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 5 related to day 3 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
DAY:4
Q: [question 1 related to day 4 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 2 related to day 4 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 3 related to day 4 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 4 related to day 4 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 5 related to day 4 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
DAY:5
Q: [question 1 related to day 5 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 2 related to day 5 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 3 related to day 5 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 4 related to day 5 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 5 related to day 5 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
DAY:6
Q: [question 1 related to day 6 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 2 related to day 6 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 3 related to day 6 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 4 related to day 6 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 5 related to day 6 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
DAY:7
Q: [question 1 related to day 7 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 2 related to day 7 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 3 related to day 7 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 4 related to day 7 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 5 related to day 7 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
MCQ_END

CODING_START
DAY:1
TASK: [beginner coding task for day 1 topic]
HINT: [helpful hint]
DAY:2
TASK: [coding task for day 2 topic]
HINT: [helpful hint]
DAY:3
TASK: [coding task for day 3 topic]
HINT: [helpful hint]
DAY:4
TASK: [coding task for day 4 topic]
HINT: [helpful hint]
DAY:5
TASK: [coding task for day 5 topic]
HINT: [helpful hint]
DAY:6
TASK: [coding task for day 6 topic]
HINT: [helpful hint]
DAY:7
TASK: [coding task for day 7 topic]
HINT: [helpful hint]
CODING_END

MOTIVATION_START
TOPIC: [language name]
STORY: [2-3 paragraph real-world success story]
DAILY_TIP: [one short powerful tip]
MOTIVATION_END

LEARNING_PACKAGE_END

NON-PROGRAMMING TOPIC RULES:
When user wants to learn a NON-programming topic:
If user says "I want to learn [topic]" WITHOUT asking for a plan:
- Give a 2-3 sentence overview only
- Ask: "Would you like me to create a weekly study plan for this and add it to your planner?"
- Wait for confirmation

If user DIRECTLY asks for a plan:
- Generate using WEEKLY_PLAN_START and WEEKLY_PLAN_END blocks:

WEEKLY_PLAN_START
Monday: [task]
...
WEEKLY_PLAN_END

CONCEPT EXPLANATION RULES:
**Quick Answer:** one or two sentences
**Explanation:** simple with analogy
**Step-by-Step:** numbered steps
**Example:** practical
**Tips:** one or two suggestions

BEHAVIOR RULES:
When user asks for CODING help: explain logic first, then give code with comments, suggest improvements.
When unclear: ask one clarifying question.

STRICT RULES:
- Only help with learning, studying, coding, academic topics
- NEVER use HTML tags in any response
- Never give one sentence answers
- Always be structured and practical
- Slogan: Fragmented hurts, not the technology

╔══════════════════════════════════════════════════════════════╗
║  ABSOLUTE OUTPUT REQUIREMENTS — FOLLOW EXACTLY               ║
╚══════════════════════════════════════════════════════════════╝

You MUST generate the MCQ block in this EXACT order with NO skipping:

DAY:1 → 5 questions
DAY:2 → 5 questions
DAY:3 → 5 questions
DAY:4 → 5 questions
DAY:5 → 5 questions
DAY:6 → 5 questions
DAY:7 → 5 questions

That is 7 day markers and 35 questions TOTAL. Not 1. Not 2. Not 4. EXACTLY 7 days.

You MUST also generate the CODING block in this EXACT order:

DAY:1 → 1 task
DAY:2 → 1 task
DAY:3 → 1 task
DAY:4 → 1 task
DAY:5 → 1 task
DAY:6 → 1 task
DAY:7 → 1 task

That is 7 day markers and 7 tasks TOTAL.

DO NOT skip from DAY:1 straight to DAY:7.
DO NOT use "..." or shortcuts.
DO NOT write "and so on" or "etc".
WRITE EVERY DAY OUT IN FULL.

Each MCQ must have:
- A "Q:" line with the question
- Four lines starting "A)" "B)" "C)" "D)"
- An "ANS:" line with one letter

Each day's content must be relevant to THAT day's topic from the weekly plan.

BEFORE YOU FINISH RESPONDING, mentally count the DAY: markers in your MCQ block.
If there are fewer than 7, you have failed the instruction. Start the MCQ block over.
"""


def build_adaptive_context(weak_topics: list, topic_avgs: dict) -> str:
    if not weak_topics and not topic_avgs:
        return ""

    lines = ["\n[STUDENT PERFORMANCE CONTEXT]"]
    lines.append(
        "The student has completed practice quizzes. "
        "Adjust responses to focus on weak areas and skip re-explaining mastered content."
    )

    weak_model   = [
        {"topic": t.rsplit(" (", 1)[0].strip(),
         "avg_score": topic_avgs.get(t.rsplit(" (", 1)[0].strip(), 0)}
        for t in weak_topics
    ]
    strong_names = [t for t, s in topic_avgs.items() if s >= 80]
    strong_model = [{"topic": t, "avg_score": topic_avgs[t]} for t in strong_names]
    user_model   = {
        "weak_topics":   weak_model,
        "strong_topics": strong_model,
        "review_due":    [],
    }
    lines.append(json.dumps(user_model, indent=2))

    if weak_topics:
        lines.append(
            "Topics needing more attention (score < 70%): " + ", ".join(weak_topics)
        )
        lines.append(
            "For these topics: increase explanation depth, add extra examples, "
            "and suggest targeted practice exercises."
        )

    if strong_names:
        lines.append(
            "Topics with strong understanding (>= 80%): "
            + ", ".join(strong_names)
            + ". Build on these without re-explaining basics."
        )

    lines.append("[END PERFORMANCE CONTEXT]\n")
    return "\n".join(lines)


def _build_prompt(
    history: list,
    user_message: str,
    performance_context: str = "",
    rag_context: str = "",
) -> str:
    parts = [f"[SYSTEM INSTRUCTION]\n{SYSTEM_INSTRUCTION.strip()}\n"]

    if rag_context:
        parts.append(
            f"Relevant knowledge:\n{rag_context}\n\nUse the above to inform your response."
        )

    if performance_context:
        parts.append(performance_context)

    if history:
        parts.append("[CONVERSATION HISTORY]")
        for msg in history:
            role = "Student" if msg["role"] == "user" else "Nexus"
            parts.append(f"{role}: {msg['content']}")
        parts.append("")

    parts.append(f"[CURRENT QUESTION]\nStudent: {user_message}\nNexus:")
    prompt = "\n".join(parts)

    prompt += """

REMINDER — BEFORE YOU REPLY CHECK THESE RULES:
1. Programming topic → generate full LEARNING_PACKAGE_START block immediately
2. Non-programming "I want to learn X" → 2-3 sentence overview then ask about plan
3. Direct plan request → generate WEEKLY_PLAN_START block immediately
4. NEVER use HTML tags
5. Always follow the exact format specified
"""
    return prompt


def _extract_weak_topic_names(performance_context: str) -> list[str]:
    if not performance_context:
        return []
    m = re.search(r"Topics needing more attention[^:]*:\s*(.+)", performance_context)
    if not m:
        return []
    raw = m.group(1)
    names = []
    for part in raw.split(","):
        name = re.sub(r"\s*\(\d+%\)", "", part).strip().lower()
        if name:
            names.append(name)
    return names


def _response_addresses_weak_topics(reply: str, weak_topics: list[str]) -> bool:
    if not weak_topics:
        return True

    reply_lower = reply.lower()
    return any(topic in reply_lower for topic in weak_topics)


def _build_reprompt(
    history: list,
    user_message: str,
    performance_context: str,
    rag_context: str,
    weak_topics: list[str],
) -> str:
    topic_list = ", ".join(weak_topics)
    reprompt_instruction = (
        f"\n[ADAPTIVE REPROMPT — STRICT]\n"
        f"Your previous response did not address the student's weak topics: {topic_list}.\n"
        f"Rewrite your response. You MUST explicitly mention and explain concepts related to: {topic_list}.\n"
        f"Tie your answer back to these areas. This is required for personalised learning.\n"
        f"[END REPROMPT]\n"
    )
    base = _build_prompt(history, user_message, performance_context, rag_context)
    return base + reprompt_instruction


def ask_ollama(
    history: list,
    user_message: str,
    performance_context: str = "",
) -> str:
    rag_context = ""
    prompt = _build_prompt(history, user_message, performance_context, rag_context)

    try:
        resp = GROQ_CLIENT.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are Nexus, a structured AI study assistant."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.3,
            max_tokens=8192,
        )
        first_reply = resp.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"Groq API error: {e}")

    # ── Adaptive loop ────────────────────────────────────────────────────────
    weak_topics = _extract_weak_topic_names(performance_context)
    if weak_topics and not _response_addresses_weak_topics(first_reply, weak_topics):
        reprompt = _build_reprompt(
            history, user_message, performance_context, rag_context, weak_topics
        )
        try:
            r2 = GROQ_CLIENT.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "You are Nexus, a structured AI study assistant."},
                    {"role": "user",   "content": reprompt}
                ],
                temperature=0.3,
                max_tokens=8192,
            )
            second_reply = r2.choices[0].message.content.strip()
            if second_reply:
                return second_reply
        except Exception:
            pass

    return first_reply


def stream_ollama(
    history: list,
    user_message: str,
    performance_context: str = "",
):
    rag_context = ""
    prompt = _build_prompt(history, user_message, performance_context, rag_context)

    first_tokens = []

    try:
        stream = GROQ_CLIENT.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are Nexus, a structured AI study assistant."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.5,
            max_tokens=8192,
            stream=True,
        )
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                first_tokens.append(token)
                yield token
    except Exception as e:
        raise RuntimeError(f"Groq stream error: {e}")

    # ── Adaptive loop after stream done ─────────────────────────────────────
    first_reply = "".join(first_tokens)
    weak_topics = _extract_weak_topic_names(performance_context)
    if weak_topics and not _response_addresses_weak_topics(first_reply, weak_topics):
        reprompt = _build_reprompt(
            history, user_message, performance_context, rag_context, weak_topics
        )
        try:
            stream2 = GROQ_CLIENT.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "You are Nexus, a structured AI study assistant."},
                    {"role": "user",   "content": reprompt}
                ],
                temperature=0.5,
                max_tokens=8192,
                stream=True,
            )
            for chunk in stream2:
                token = chunk.choices[0].delta.content or ""
                if token:
                    yield token
        except Exception:
            pass


def check_ollama_status() -> dict:
    """Kept for backward compatibility — now checks Groq instead."""
    try:
        GROQ_CLIENT.models.list()
        return {"ok": True, "model": GROQ_MODEL, "model_loaded": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}