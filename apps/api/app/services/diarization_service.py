"""Diarization service for alignment of speaker intervals to transcript segments and DB persistence."""

import logging
import uuid
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting import Speaker
from app.models.transcript import Transcript, TranscriptSegment
from app.services.diarization import DiarizationResult, SpeakerInterval, get_diarization_provider

logger = logging.getLogger(__name__)


class DiarizationService:
    """Core domain service for alignment of diarized speaker intervals to transcript segments."""

    @staticmethod
    def align_speakers_to_segments(
        segments: List[TranscriptSegment],
        intervals: List[SpeakerInterval],
        tolerance_seconds: float = 0.5,
    ) -> Dict[uuid.UUID, Optional[str]]:
        """Align transcript segments to diarization intervals using Maximum Temporal Overlap strategy.

        Strategy:
        For each TranscriptSegment S with time range [start_time, end_time]:
        1. Calculate temporal overlap with all SpeakerIntervals D.
        2. Sum overlap durations per speaker_label.
        3. The speaker_label with maximum total overlap duration wins.
        4. If no overlapping interval exists (max overlap == 0), fallback to nearest interval within tolerance.
        5. In case of ties, fallback to earliest start time or alphabetical label.

        Returns:
            Dict mapping segment.id -> speaker_label (e.g., 'speaker_0' or None)
        """
        if not segments:
            return {}

        segment_speaker_map: Dict[uuid.UUID, Optional[str]] = {}

        for seg in segments:
            s_start = float(seg.start_time)
            s_end = float(seg.end_time)

            overlap_by_label: Dict[str, float] = {}

            for inter in intervals:
                d_start = float(inter.start_time)
                d_end = float(inter.end_time)

                # Compute temporal intersection
                overlap_start = max(s_start, d_start)
                overlap_end = min(s_end, d_end)
                overlap_len = max(0.0, overlap_end - overlap_start)

                if overlap_len > 0:
                    label = inter.speaker_label
                    overlap_by_label[label] = overlap_by_label.get(label, 0.0) + overlap_len

            if overlap_by_label:
                # Maximum temporal overlap label
                best_label = max(overlap_by_label.items(), key=lambda item: (item[1], item[0]))[0]
                segment_speaker_map[seg.id] = best_label
            else:
                # Fallback: Find nearest interval within tolerance
                nearest_label = None
                min_dist = float("inf")

                for inter in intervals:
                    d_start = float(inter.start_time)
                    d_end = float(inter.end_time)

                    # Distance between intervals
                    if d_end < s_start:
                        dist = s_start - d_end
                    elif d_start > s_end:
                        dist = d_start - s_end
                    else:
                        dist = 0.0

                    if dist < min_dist and dist <= tolerance_seconds:
                        min_dist = dist
                        nearest_label = inter.speaker_label

                segment_speaker_map[seg.id] = nearest_label

        return segment_speaker_map

    @classmethod
    async def process_diarization(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        audio_path: str,
    ) -> Dict[str, int]:
        """Execute end-to-end diarization pipeline, speaker upsertion, and transcript alignment.

        Args:
            db: Async database session.
            meeting_id: UUID of meeting being diarized.
            audio_path: Path to normalized WAV audio file.

        Returns:
            Dict containing summary metrics (speakers_count, segments_aligned).
        """
        # 1. Fetch transcript and segments for the meeting
        t_stmt = (
            select(Transcript)
            .where(Transcript.meeting_id == meeting_id)
            .order_by(Transcript.created_at.desc())
        )
        transcript = (await db.execute(t_stmt)).scalars().first()

        if not transcript:
            logger.warning(f"No transcript found for meeting {meeting_id}. Skipping diarization.")
            return {"speakers_count": 0, "segments_aligned": 0}

        seg_stmt = (
            select(TranscriptSegment)
            .where(TranscriptSegment.transcript_id == transcript.id)
            .order_by(TranscriptSegment.sequence_order.asc())
        )
        segments = list((await db.execute(seg_stmt)).scalars().all())

        if not segments:
            logger.warning(f"Transcript {transcript.id} contains 0 segments. Skipping diarization.")
            return {"speakers_count": 0, "segments_aligned": 0}

        # 2. Execute Diarization Provider
        provider = get_diarization_provider()
        diarization_result: DiarizationResult = await provider.diarize(audio_path=audio_path)

        if not diarization_result.segments:
            logger.warning(f"Diarization returned 0 speaker intervals for meeting {meeting_id}.")
            return {"speakers_count": 0, "segments_aligned": 0}

        # 3. Retrieve or create Speaker records for meeting idempotently
        spk_stmt = select(Speaker).where(Speaker.meeting_id == meeting_id)
        existing_speakers = list((await db.execute(spk_stmt)).scalars().all())
        speaker_by_label: Dict[str, Speaker] = {s.label: s for s in existing_speakers}

        unique_labels = sorted(list({inter.speaker_label for inter in diarization_result.segments}))

        for label in unique_labels:
            if label not in speaker_by_label:
                # Create standard label speaker if not present
                new_speaker = Speaker(
                    id=uuid.uuid4(),
                    meeting_id=meeting_id,
                    label=label,
                    name=None,  # Unmapped initial display name
                )
                db.add(new_speaker)
                speaker_by_label[label] = new_speaker

        await db.flush()

        # 4. Perform Maximum Temporal Overlap Alignment
        segment_label_map = cls.align_speakers_to_segments(
            segments=segments,
            intervals=diarization_result.segments,
        )

        # 5. Assign speaker_id to TranscriptSegment records
        aligned_count = 0
        for seg in segments:
            label = segment_label_map.get(seg.id)
            if label and label in speaker_by_label:
                seg.speaker_id = speaker_by_label[label].id
                aligned_count += 1
            else:
                seg.speaker_id = None

        await db.commit()

        logger.info(
            f"[DiarizationService] Completed diarization for meeting={meeting_id}: "
            f"created/verified {len(unique_labels)} speakers, aligned {aligned_count}/{len(segments)} segments."
        )

        return {
            "speakers_count": len(unique_labels),
            "segments_aligned": aligned_count,
        }
