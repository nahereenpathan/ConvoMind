"""Transcript export service generating multi-format outputs (TXT, Markdown, SRT, WebVTT, JSON)."""

import json
from typing import List, Tuple
from app.models.meeting import Meeting
from app.models.transcript import Transcript, TranscriptSegment


class TranscriptExportService:
    """Service to format and export transcripts and their segments into various file formats."""

    @staticmethod
    def _format_time(seconds: float, separator: str = ",") -> str:
        """Format seconds into HH:MM:SS,mmm or HH:MM:SS.mmm."""
        total_millis = max(0, int(round(seconds * 1000)))
        hours = total_millis // 3_600_000
        rem = total_millis % 3_600_000
        minutes = rem // 60_000
        rem = rem % 60_000
        secs = rem // 1_000
        millis = rem % 1_000
        return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"

    @staticmethod
    def _get_speaker_label(segment: TranscriptSegment) -> str:
        """Resolve speaker name or label for a segment."""
        if segment.speaker:
            return segment.speaker.name or segment.speaker.label
        return ""

    @classmethod
    def export_txt(
        cls,
        meeting: Meeting,
        transcript: Transcript,
        segments: List[TranscriptSegment],
    ) -> Tuple[str, str, str]:
        """Export transcript as human-readable plain text.

        Returns: (content, media_type, filename)
        """
        lines = [
            f"Transcript: {meeting.title}",
            f"Date: {transcript.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if transcript.created_at else 'N/A'}",
            f"Duration: {transcript.duration or 0:.1f}s | Words: {transcript.word_count} | Language: {transcript.language}",
            "-" * 60,
            "",
        ]

        for seg in segments:
            speaker = cls._get_speaker_label(seg)
            start_str = cls._format_time(seg.start_time, separator=".")
            if speaker:
                lines.append(f"[{start_str}] {speaker}: {seg.text}")
            else:
                lines.append(f"[{start_str}] {seg.text}")

        content = "\n".join(lines) + "\n"
        filename = f"transcript_{meeting.id}.txt"
        return content, "text/plain; charset=utf-8", filename

    @classmethod
    def export_markdown(
        cls,
        meeting: Meeting,
        transcript: Transcript,
        segments: List[TranscriptSegment],
    ) -> Tuple[str, str, str]:
        """Export transcript formatted with Markdown headers and metadata.

        Returns: (content, media_type, filename)
        """
        lines = [
            f"# Meeting Transcript: {meeting.title}",
            "",
            f"- **Date:** {transcript.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if transcript.created_at else 'N/A'}",
            f"- **Language:** `{transcript.language}`",
            f"- **Duration:** `{transcript.duration or 0:.1f} seconds`",
            f"- **Word Count:** {transcript.word_count}",
            "",
            "---",
            "",
            "## Dialogue",
            "",
        ]

        for seg in segments:
            speaker = cls._get_speaker_label(seg)
            start_str = cls._format_time(seg.start_time, separator=".")
            end_str = cls._format_time(seg.end_time, separator=".")
            header = f"### [{start_str} - {end_str}]"
            if speaker:
                header += f" {speaker}"
            lines.append(header)
            lines.append("")
            lines.append(seg.text)
            lines.append("")

        content = "\n".join(lines)
        filename = f"transcript_{meeting.id}.md"
        return content, "text/markdown; charset=utf-8", filename

    @classmethod
    def export_srt(
        cls,
        meeting: Meeting,
        transcript: Transcript,
        segments: List[TranscriptSegment],
    ) -> Tuple[str, str, str]:
        """Export transcript as SubRip (.srt) subtitle cues with comma millisecond separators.

        Returns: (content, media_type, filename)
        """
        blocks = []
        for idx, seg in enumerate(segments, start=1):
            start_str = cls._format_time(seg.start_time, separator=",")
            end_str = cls._format_time(seg.end_time, separator=",")
            speaker = cls._get_speaker_label(seg)

            text = f"{speaker}: {seg.text}" if speaker else seg.text
            blocks.append(f"{idx}\n{start_str} --> {end_str}\n{text}")

        content = "\n\n".join(blocks) + "\n" if blocks else ""
        filename = f"transcript_{meeting.id}.srt"
        return content, "application/x-subrip; charset=utf-8", filename

    @classmethod
    def export_vtt(
        cls,
        meeting: Meeting,
        transcript: Transcript,
        segments: List[TranscriptSegment],
    ) -> Tuple[str, str, str]:
        """Export transcript as WebVTT (.vtt) cues with dot millisecond separators and voice tags.

        Returns: (content, media_type, filename)
        """
        blocks = ["WEBVTT", f"NOTE Transcript for meeting: {meeting.title}"]

        for idx, seg in enumerate(segments, start=1):
            start_str = cls._format_time(seg.start_time, separator=".")
            end_str = cls._format_time(seg.end_time, separator=".")
            speaker = cls._get_speaker_label(seg)

            if speaker:
                cue_text = f"<v {speaker}>{seg.text}</v>"
            else:
                cue_text = seg.text

            blocks.append(f"{idx}\n{start_str} --> {end_str}\n{cue_text}")

        content = "\n\n".join(blocks) + "\n"
        filename = f"transcript_{meeting.id}.vtt"
        return content, "text/vtt; charset=utf-8", filename

    @classmethod
    def export_json(
        cls,
        meeting: Meeting,
        transcript: Transcript,
        segments: List[TranscriptSegment],
    ) -> Tuple[str, str, str]:
        """Export complete transcript and segment list as structured JSON.

        Returns: (content, media_type, filename)
        """
        data = {
            "meeting_id": str(meeting.id),
            "meeting_title": meeting.title,
            "transcript_id": str(transcript.id),
            "status": transcript.status.value,
            "language": transcript.language,
            "duration": transcript.duration,
            "word_count": transcript.word_count,
            "confidence_score": transcript.confidence_score,
            "created_at": transcript.created_at.isoformat() if transcript.created_at else None,
            "segments": [
                {
                    "id": str(s.id),
                    "sequence_order": s.sequence_order,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "text": s.text,
                    "confidence": s.confidence,
                    "speaker_id": str(s.speaker_id) if s.speaker_id else None,
                    "speaker_label": s.speaker.label if s.speaker else None,
                    "speaker_name": s.speaker.name if s.speaker else None,
                }
                for s in segments
            ],
        }

        content = json.dumps(data, indent=2)
        filename = f"transcript_{meeting.id}.json"
        return content, "application/json; charset=utf-8", filename
