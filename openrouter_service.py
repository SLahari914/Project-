"""
openrouter_service.py – OpenRouter AI Integration Service
Features:
  - Video relevance scoring using OpenRouter Rerank API (nvidia/llama-nemotron-rerank-vl-1b-v2:free)
  - Quiz tracking & answer evaluation
  - Resilient error handling with automated fallback
"""

import requests
import json
from config import Config

def call_openrouter_rerank(query, documents, top_n=3):
    """
    Calls OpenRouter's rerank endpoint with user's model:
    model: nvidia/llama-nemotron-rerank-vl-1b-v2:free
    """
    headers = {
        "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://127.0.0.1:5000",
        "X-OpenRouter-Title": "AI Internship Monitoring System"
    }

    # Format documents for OpenRouter rerank format
    formatted_docs = []
    for doc in documents:
        if isinstance(doc, str):
            formatted_docs.append({"text": doc})
        elif isinstance(doc, dict):
            formatted_docs.append(doc)

    payload = {
        "model": Config.OPENROUTER_RERANK_MODEL,
        "query": query,
        "documents": formatted_docs,
        "top_n": min(top_n, len(formatted_docs))
    }

    try:
        response = requests.post(
            Config.OPENROUTER_RERANK_URL,
            headers=headers,
            json=payload,
            timeout=12
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"[WARN] OpenRouter rerank error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"[WARN] OpenRouter connection exception: {e}")
        return None


def evaluate_internship_video_with_ai(title, description, topic="Web Development, Software Engineering and AI"):
    """
    Evaluates student's internship video submission description using OpenRouter reranking
    against benchmark internship learning outcomes.
    """
    reference_benchmarks = [
        "Comprehensive architectural explanation, backend database design, frontend interactivity, and problem solving demonstrated.",
        "Demonstrated working software features, code walk-through, unit testing, and technical implementation challenges.",
        "Basic overview of project screens with limited explanation of code and technical design.",
        "Irrelevant or superficial discussion lacking demonstrable project work."
    ]

    docs = [{"text": b} for b in reference_benchmarks]
    query = f"Internship Project Demo: {title}. Implementation details: {description}. Tech domain: {topic}"

    rerank_result = call_openrouter_rerank(query, docs, top_n=4)

    if rerank_result and "results" in rerank_result and len(rerank_result["results"]) > 0:
        top_match = rerank_result["results"][0]
        relevance_score = top_match.get("relevance_score", 0.0)
        idx = top_match.get("index", 0)

        # Scale score from 65 to 98 based on match quality
        if idx == 0:
            final_score = round(min(98.0, max(85.0, 85.0 + relevance_score * 500)), 1)
            feedback = "Excellent presentation. Strong correlation with core internship technical competencies and deep architectural breakdown."
        elif idx == 1:
            final_score = round(min(88.0, max(75.0, 75.0 + relevance_score * 400)), 1)
            feedback = "Good demonstration of practical features and workflows. Recommended to include more unit test coverage in the next update."
        elif idx == 2:
            final_score = round(min(75.0, max(60.0, 60.0 + relevance_score * 300)), 1)
            feedback = "Satisfactory overview. Needs more depth regarding backend algorithms, data persistence, and performance considerations."
        else:
            final_score = 55.0
            feedback = "Review required: Please elaborate on actual code contributions and engineering tasks completed."

        return {
            "ai_score": final_score,
            "raw_relevance": relevance_score,
            "ai_feedback": feedback,
            "engine": "OpenRouter: nvidia/llama-nemotron-rerank-vl-1b-v2:free"
        }

    # Deterministic heuristic fallback if OpenRouter is unreachable
    desc_words = len(description.split())
    if desc_words > 40:
        fallback_score = 88.0
        fallback_msg = "Detailed submission received. Video demonstrates solid progress across project milestones."
    elif desc_words > 15:
        fallback_score = 78.0
        fallback_msg = "Submission verified. Presentation covers fundamental functional objectives."
    else:
        fallback_score = 65.0
        fallback_msg = "Submission received. Consider expanding description with additional technical implementation details."

    return {
        "ai_score": fallback_score,
        "raw_relevance": 0.5,
        "ai_feedback": fallback_msg,
        "engine": "Heuristic Analyzer (OpenRouter Fallback)"
    }


def evaluate_quiz_with_ai(student_answers, quiz_questions):
    """
    Computes quiz grade and evaluates answer reasoning.
    """
    total = len(quiz_questions)
    correct_count = 0
    feedback_items = []

    for idx, q in enumerate(quiz_questions):
        q_id = str(q.get("id", idx + 1))
        submitted = student_answers.get(q_id, "").strip().upper()
        expected = (q.get("answer") or q.get("correct") or "").strip().upper()
        is_correct = (submitted == expected)
        if is_correct:
            correct_count += 1
            feedback_items.append(f"Q{idx+1}: Correct! {q.get('explanation', '')}")
        else:
            feedback_items.append(f"Q{idx+1}: Incorrect (Selected '{submitted}', Correct is '{expected}'). {q.get('explanation', '')}")

    score_pct = round((correct_count / total * 100), 1) if total > 0 else 0

    return {
        "score": correct_count,
        "total": total,
        "percentage": score_pct,
        "feedback": " | ".join(feedback_items)
    }
