"""Transcript segmentation and sentence-aware chunking service."""

from dataclasses import dataclass, field
import hashlib
import re
from typing import Any, Dict, List, Optional
import uuid

from app.core.config import settings
from app.models.transcript import TranscriptSegment


@dataclass
class ChunkData:
    """Structured representation of a transcript text chunk."""

    chunk_index: int
    content: str
    content_hash: str
    start_segment_id: Optional[uuid.UUID]
    end_segment_id: Optional[uuid.UUID]
    start_time: float
    end_time: float
    token_count: int
    segment_ids: List[uuid.UUID] = field(default_factory=list)
    speaker_labels: List[str] = field(default_factory=list)


class TranscriptChunker:
    """Sentence-aware chunker for transcript segments preserving timestamps and source references."""

    def __init__(
        self,
        chunk_size: int = settings.EMBEDDING_CHUNK_SIZE,
        chunk_overlap: int = settings.EMBEDDING_CHUNK_OVERLAP,
    ):
        self.chunk_size = max(chunk_size, 100)
        self.chunk_overlap = max(min(chunk_overlap, self.chunk_size // 2), 0)

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text on sentence boundaries (period, question mark, exclamation)."""
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [s.strip() for s in sentences if s.strip()]

    def _compute_hash(self, transcript_id: uuid.UUID, index: int, content: str) -> str:
        """Calculate deterministic SHA-256 content hash."""
        raw_key = f"{transcript_id}:{index}:{content}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def chunk_segments(
        self,
        transcript_id: uuid.UUID,
        segments: List[TranscriptSegment],
    ) -> List[ChunkData]:
        """Chunk an ordered list of TranscriptSegment instances into ChunkData objects."""
        if not segments:
            return []

        chunks: List[ChunkData] = []
        current_text_parts: List[str] = []
        current_segments: List[TranscriptSegment] = []
        current_speakers: List[str] = []
        current_len = 0
        chunk_idx = 0

        for seg in segments:
            speaker_str = None
            if hasattr(seg, "speaker") and seg.speaker:
                speaker_str = seg.speaker.name or seg.speaker.label
            elif hasattr(seg, "speaker_name") and getattr(seg, "speaker_name"):
                speaker_str = getattr(seg, "speaker_name")

            formatted_seg_text = (
                f"[{speaker_str}]: {seg.text}" if speaker_str else seg.text
            )

            # Check if adding this segment exceeds chunk_size
            if current_len > 0 and (current_len + len(formatted_seg_text)) > self.chunk_size:
                # Flush current chunk
                content = "\n".join(current_text_parts)
                start_seg = current_segments[0]
                end_seg = current_segments[-1]
                content_hash = self._compute_hash(transcript_id, chunk_idx, content)
                words = content.split()

                chunks.append(
                    ChunkData(
                        chunk_index=chunk_idx,
                        content=content,
                        content_hash=content_hash,
                        start_segment_id=start_seg.id,
                        end_segment_id=end_seg.id,
                        start_time=start_seg.start_time,
                        end_time=end_seg.end_time,
                        token_count=len(words),
                        segment_ids=[s.id for s in current_segments if s.id],
                        speaker_labels=list(set(current_speakers)),
                    )
                )
                chunk_idx += 1

                # Handle overlap: keep ending segments whose length <= chunk_overlap
                overlap_segments: List[TranscriptSegment] = []
                overlap_parts: List[str] = []
                overlap_speakers: List[str] = []
                overlap_len = 0

                for prev_seg in reversed(current_segments):
                    p_speaker = None
                    if hasattr(prev_seg, "speaker") and prev_seg.speaker:
                        p_speaker = prev_seg.speaker.name or prev_seg.speaker.label
                    p_text = f"[{p_speaker}]: {prev_seg.text}" if p_speaker else prev_seg.text

                    if overlap_len + len(p_text) <= self.chunk_overlap:
                        overlap_segments.insert(0, prev_seg)
                        overlap_parts.insert(0, p_text)
                        if p_speaker:
                            overlap_speakers.append(p_speaker)
                        overlap_len += len(p_text)
                    else:
                        break

                current_segments = overlap_segments
                current_text_parts = overlap_parts
                current_speakers = overlap_speakers
                current_len = overlap_len

            # Append current segment
            current_segments.append(seg)
            current_text_parts.append(formatted_seg_text)
            if speaker_str:
                current_speakers.append(speaker_str)
            current_len += len(formatted_seg_text)

        # Flush final remaining chunk
        if current_segments:
            content = "\n".join(current_text_parts)
            start_seg = current_segments[0]
            end_seg = current_segments[-1]
            content_hash = self._compute_hash(transcript_id, chunk_idx, content)
            words = content.split()

            chunks.append(
                ChunkData(
                    chunk_index=chunk_idx,
                    content=content,
                    content_hash=content_hash,
                    start_segment_id=start_seg.id,
                    end_segment_id=end_seg.id,
                    start_time=start_seg.start_time,
                    end_time=end_seg.end_time,
                    token_count=len(words),
                    segment_ids=[s.id for s in current_segments if s.id],
                    speaker_labels=list(set(current_speakers)),
                )
            )

        return chunks
