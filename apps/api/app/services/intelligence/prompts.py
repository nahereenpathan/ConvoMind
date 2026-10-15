"""System prompts and prompt assembly utilities for AI meeting intelligence."""

from typing import Any, Dict, List, Optional

SYSTEM_PROMPT = """You are an elite Chief of Staff and Executive Meeting Analyst for ConvoMind.
Your task is to analyze the provided meeting transcript and extract high-value, structured meeting intelligence.

CRITICAL INSTRUCTIONS & GROUND TRUTH RULES:
1. STRICT ACCURACY: Rely ONLY on statements and facts explicitly mentioned in the transcript. Do NOT fabricate, infer, or extrapolate information that was not said.
2. NO HALLUCINATION OF DECISIONS: A decision is a finalized choice, commitment, or agreed consensus. Do NOT convert open suggestions, brainstorming ideas, or proposals into decisions unless explicitly agreed upon.
3. STRICT ACTION ITEM EXTRACTION:
   - An action item MUST be an explicit, actionable task, assignment, or deliverable that a specific individual or team committed to completing (e.g. "Arjun will complete backend development and testing by October 19, 2026").
   - Extract the assignee name as `assignee_name` only if explicitly mentioned in dialogue. Do NOT invent assignees. Leave null if unassigned.
   - Extract target deadlines or dates as `due_date_str` when mentioned. Do NOT invent deadlines. Leave null if no deadline was stated.
   - DO NOT extract generic statements, meeting introductions, software/product definitions, meeting agendas, or decisions as action items (e.g. "It is an AI powered meeting assistant..." or "First, we will focus on meeting summaries..." are NOT action items).
4. TIMESTAMPS: For decisions, action items, and questions, provide the exact `timestamp_marker` (in seconds) corresponding to the utterance timestamp cue in the transcript. Do not invent arbitrary numbers.
5. EMPTY ON UNAVAILABLE: If no decisions, risks, or questions occurred in the discussion, return an empty list rather than inventing placeholders.
6. PRESERVE SPECIFICS: Faithfully retain all specific dates, metrics, technical terms, system components, numbers, and person names mentioned in discussion.
7. CLEAR DISTINCTIONS:
   - Executive Summary: Concise 2-4 sentences highlighting the main purpose and core outcomes.
   - Detailed Summary: In-depth narrative reviewing the flow of conversation across all topics.
   - Risks & Concerns: Explicitly raised blockers, technical uncertainties, timeline threats, or dependencies.
   - Requirements & Notes: Specifications, architectural constraints, and compliance or operational prerequisites.
   - Follow-up Suggestions: Next steps, future discussion items, or recommended checks.
"""


def format_seconds_to_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS.mmm."""
    total_millis = max(0, int(round(seconds * 1000)))
    hours = total_millis // 3_600_000
    rem = total_millis % 3_600_000
    minutes = rem // 60_000
    rem = rem % 60_000
    secs = rem // 1_000
    millis = rem % 1_000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def build_transcript_prompt(
    transcript_text: str,
    segments: Optional[List[Dict[str, Any]]] = None,
    max_chars: int = 350_000,
) -> str:
    """Construct formatted transcript dialogue for LLM ingestion with token safety guards."""
    formatted_lines: List[str] = []

    if segments and len(segments) > 0:
        formatted_lines.append("--- BEGIN MEETING TRANSCRIPT DIALOGUE ---")
        for seg in segments:
            start_time = float(seg.get("start_time", 0.0))
            time_str = format_seconds_to_timestamp(start_time)

            speaker = (
                seg.get("speaker_name")
                or seg.get("speaker_label")
                or (seg.get("speaker", {}).get("name") if isinstance(seg.get("speaker"), dict) else None)
                or (seg.get("speaker", {}).get("label") if isinstance(seg.get("speaker"), dict) else None)
                or "Speaker"
            )
            text = seg.get("text", "").strip()
            if text:
                formatted_lines.append(f"[{time_str}] ({start_time:.1f}s) {speaker}: {text}")
        formatted_lines.append("--- END MEETING TRANSCRIPT DIALOGUE ---")
    else:
        formatted_lines.append("--- BEGIN MEETING TRANSCRIPT TEXT ---")
        formatted_lines.append(transcript_text.strip())
        formatted_lines.append("--- END MEETING TRANSCRIPT TEXT ---")

    prompt_body = "\n".join(formatted_lines)

    # Token/Character safety truncation guard
    if len(prompt_body) > max_chars:
        prompt_body = (
            prompt_body[:max_chars]
            + "\n... [TRANSCRIPT TRUNCATED DUE TO MAXIMUM CONTEXT LENGTH LIMIT] ..."
        )

    return prompt_body
