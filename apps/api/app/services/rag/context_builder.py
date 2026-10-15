"""RAG Context Builder for converting retrieved vector chunks into structured prompt context."""

from typing import Dict, List, Tuple
from app.services.embedding.search_service import VectorSearchResult


class ContextBuilder:
    """Formats retrieved vector search results into grounded prompt context blocks."""

    @staticmethod
    def build_context(
        results: List[VectorSearchResult],
        meeting_titles: Dict[str, str] = None,
    ) -> Tuple[str, List[Dict]]:
        """Format retrieved search chunks into readable LLM context string and metadata source references."""
        if not results:
            return "[NO RETRIEVED CONTEXT AVAILABLE]", []

        meeting_titles = meeting_titles or {}
        context_lines: List[str] = []
        sources: List[Dict] = []

        for idx, res in enumerate(results, 1):
            m_title = meeting_titles.get(str(res.meeting_id)) or f"Meeting {str(res.meeting_id)[:8]}"
            valid_speakers = [s for s in res.speaker_labels if s and s.strip() and s.strip() != "Unspecified Speaker"]
            speakers = ", ".join(valid_speakers) if valid_speakers else "Unknown Speaker"

            start_t = f"{res.start_time:.1f}s" if res.start_time is not None else "N/A"
            end_t = f"{res.end_time:.1f}s" if res.end_time is not None else "N/A"

            context_lines.append(
                f"Meeting:\n{m_title}\n\n"
                f"Source #{idx}:\n"
                f"Speaker: {speakers}\n"
                f"Timestamp: {start_t} - {end_t}\n"
                f"Transcript:\n"
                f"{res.content.strip()}\n"
            )

            sources.append({
                "source_index": idx,
                "meeting_id": str(res.meeting_id),
                "transcript_id": str(res.transcript_id),
                "start_segment_id": str(res.start_segment_id) if res.start_segment_id else None,
                "end_segment_id": str(res.end_segment_id) if res.end_segment_id else None,
                "meeting_title": m_title,
                "text": res.content.strip(),
                "text_excerpt": res.content.strip(),
                "start_time": res.start_time,
                "end_time": res.end_time,
                "speaker": speakers,
                "speaker_labels": valid_speakers if valid_speakers else ["Unknown Speaker"],
                "score": res.similarity_score,
                "similarity_score": res.similarity_score,
            })

        formatted_context = "\n---\n".join(context_lines)
        return formatted_context, sources
