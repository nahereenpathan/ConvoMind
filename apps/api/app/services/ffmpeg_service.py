"""FFmpeg and FFprobe media inspection and processing service."""

import json
import logging
import os
import shutil
import subprocess
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class FFmpegService:
    """Service wrapping ffmpeg and ffprobe CLI tools for media probing and conversion."""

    def __init__(
        self,
        ffmpeg_binary: Optional[str] = None,
        ffprobe_binary: Optional[str] = None,
    ):
        self.ffmpeg_path = ffmpeg_binary or shutil.which("ffmpeg") or "ffmpeg"
        self.ffprobe_path = ffprobe_binary or shutil.which("ffprobe") or "ffprobe"

    def is_available(self) -> bool:
        """Check if media processing is available via CLI or PyAV library."""
        has_ffmpeg = bool(shutil.which(self.ffmpeg_path) or os.path.isfile(self.ffmpeg_path))
        has_ffprobe = bool(shutil.which(self.ffprobe_path) or os.path.isfile(self.ffprobe_path))
        if has_ffmpeg and has_ffprobe:
            return True
        try:
            import av  # noqa: F401
            return True
        except ImportError:
            return False

    def _probe_with_pyav(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Probe media metadata using PyAV (bundled FFmpeg C libraries)."""
        try:
            import av
            with av.open(file_path) as container:
                duration_seconds: Optional[int] = None
                if container.duration is not None and av.time_base:
                    try:
                        duration_seconds = int(round(float(container.duration) / av.time_base))
                    except Exception:
                        duration_seconds = None

                audio_stream = next((s for s in container.streams if s.type == "audio"), None)
                video_stream = next((s for s in container.streams if s.type == "video"), None)

                if (duration_seconds is None or duration_seconds == 0) and audio_stream and audio_stream.duration and audio_stream.time_base:
                    try:
                        duration_seconds = int(round(float(audio_stream.duration * audio_stream.time_base)))
                    except Exception:
                        pass

                sample_rate = audio_stream.rate if audio_stream else None
                channels = audio_stream.channels if audio_stream else None
                audio_codec = (
                    audio_stream.codec_context.name
                    if (audio_stream and audio_stream.codec_context)
                    else None
                )

                return {
                    "duration_seconds": duration_seconds,
                    "format_name": container.format.name if container.format else None,
                    "bit_rate": container.bit_rate,
                    "has_audio": audio_stream is not None,
                    "has_video": video_stream is not None,
                    "audio_codec": audio_codec,
                    "sample_rate": sample_rate,
                    "channels": channels,
                }
        except Exception as exc:
            logger.warning(f"PyAV media probe failed on {file_path}: {exc}")
            return None

    def _extract_with_pyav(
        self,
        input_path: str,
        output_path: str,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> bool:
        """Extract and normalize audio to 16kHz mono WAV using PyAV."""
        try:
            import av
            layout = "mono" if channels == 1 else "stereo"
            resampler = av.AudioResampler(format="s16", layout=layout, rate=sample_rate)
            with av.open(input_path) as in_c:
                audio_streams = [s for s in in_c.streams if s.type == "audio"]
                if not audio_streams:
                    logger.warning(f"No audio stream found in {input_path}")
                    return False
                with av.open(output_path, mode="w", format="wav") as out_c:
                    out_stream = out_c.add_stream("pcm_s16le", rate=sample_rate)
                    out_stream.layout = layout
                    for frame in in_c.decode(audio=0):
                        resampled_frames = resampler.resample(frame)
                        for r_frame in resampled_frames:
                            for packet in out_stream.encode(r_frame):
                                out_c.mux(packet)
                    for packet in out_stream.encode(None):
                        out_c.mux(packet)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as exc:
            logger.error(f"PyAV audio extraction failed on {input_path}: {type(exc).__name__}: {exc}")
            return False

    def probe_media(self, file_path: str) -> Dict[str, Any]:
        """Inspect media file using ffprobe (with PyAV fallback) and extract metadata."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Media file not found: {file_path}")

        # Check if ffprobe CLI binary is present
        has_ffprobe_cli = bool(shutil.which(self.ffprobe_path) or os.path.isfile(self.ffprobe_path))
        if not has_ffprobe_cli:
            pyav_res = self._probe_with_pyav(file_path)
            if pyav_res:
                return pyav_res

        command = [
            self.ffprobe_path,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if result.returncode != 0:
                logger.warning(
                    f"ffprobe failed on {file_path} with code {result.returncode}: {result.stderr}"
                )
                pyav_res = self._probe_with_pyav(file_path)
                if pyav_res:
                    return pyav_res
                return {
                    "duration_seconds": None,
                    "format_name": None,
                    "bit_rate": None,
                    "has_audio": False,
                    "has_video": False,
                    "audio_codec": None,
                    "sample_rate": None,
                    "channels": None,
                    "error": result.stderr,
                }

            data = json.loads(result.stdout)
            format_info = data.get("format", {})
            streams = data.get("streams", [])

            # Extract duration (try format container first, then audio/video stream)
            raw_duration = format_info.get("duration")
            if not raw_duration:
                for stream in streams:
                    if stream.get("duration"):
                        raw_duration = stream.get("duration")
                        break

            duration_seconds: Optional[int] = None
            if raw_duration:
                try:
                    duration_seconds = int(round(float(raw_duration)))
                except (ValueError, TypeError):
                    duration_seconds = None

            # Probe stream types
            audio_stream = next(
                (s for s in streams if s.get("codec_type") == "audio"), None
            )
            video_stream = next(
                (s for s in streams if s.get("codec_type") == "video"), None
            )

            bit_rate = None
            if format_info.get("bit_rate"):
                try:
                    bit_rate = int(format_info.get("bit_rate"))
                except (ValueError, TypeError):
                    pass

            return {
                "duration_seconds": duration_seconds,
                "format_name": format_info.get("format_name"),
                "bit_rate": bit_rate,
                "has_audio": audio_stream is not None,
                "has_video": video_stream is not None,
                "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
                "sample_rate": int(audio_stream.get("sample_rate")) if audio_stream and audio_stream.get("sample_rate") else None,
                "channels": int(audio_stream.get("channels")) if audio_stream and audio_stream.get("channels") else None,
            }

        except (subprocess.SubprocessError, FileNotFoundError, Exception) as exc:
            logger.info(f"ffprobe CLI unavailable or errored ({exc}). Trying PyAV fallback.")
            pyav_res = self._probe_with_pyav(file_path)
            if pyav_res:
                return pyav_res

            if file_path.lower().endswith(".wav"):
                try:
                    import wave
                    with wave.open(file_path, "rb") as wf:
                        frames = wf.getnframes()
                        rate = wf.getframerate()
                        dur = int(round(frames / float(rate))) if rate else 0
                        return {
                            "duration_seconds": dur,
                            "format_name": "wav",
                            "bit_rate": None,
                            "has_audio": True,
                            "has_video": False,
                            "audio_codec": "pcm_s16le",
                            "sample_rate": rate,
                            "channels": wf.getnchannels(),
                        }
                except Exception:
                    pass
            return {
                "duration_seconds": None,
                "format_name": None,
                "bit_rate": None,
                "has_audio": False,
                "has_video": False,
                "error": str(exc),
            }

    def extract_audio_for_stt(
        self,
        input_path: str,
        output_path: str,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> bool:
        """Convert input audio/video into a 16kHz mono WAV file optimized for Whisper/STT."""
        if not os.path.exists(input_path):
            logger.error(f"Input file not found for audio extraction: {input_path}")
            return False

        # Path traversal guard: verify path does not contain relative escapes
        if ".." in input_path or ".." in output_path:
            logger.error("Path traversal detected in audio extraction paths.")
            return False

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        has_ffmpeg_cli = bool(shutil.which(self.ffmpeg_path) or os.path.isfile(self.ffmpeg_path))
        if not has_ffmpeg_cli:
            pyav_ok = self._extract_with_pyav(input_path, output_path, sample_rate, channels)
            if pyav_ok:
                return True
            if input_path.lower().endswith(".wav"):
                try:
                    import wave
                    with wave.open(input_path, "rb") as wf:
                        if wf.getnframes() > 0:
                            shutil.copyfile(input_path, output_path)
                            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
                except Exception:
                    return False
            return False

        command = [
            self.ffmpeg_path,
            "-y",
            "-i",
            input_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            output_path,
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if result.returncode != 0:
                sanitized_err = (result.stderr or "")[:300].strip()
                logger.warning(
                    f"ffmpeg audio extraction failed (exit {result.returncode}): {sanitized_err}. Attempting PyAV fallback."
                )
                pyav_ok = self._extract_with_pyav(input_path, output_path, sample_rate, channels)
                if pyav_ok:
                    return True
                if input_path.lower().endswith(".wav"):
                    try:
                        import wave
                        with wave.open(input_path, "rb") as wf:
                            if wf.getnframes() > 0:
                                shutil.copyfile(input_path, output_path)
                                return os.path.exists(output_path) and os.path.getsize(output_path) > 0
                    except Exception:
                        return False
                return False

            return (
                os.path.exists(output_path)
                and os.path.getsize(output_path) > 0
            )
        except (subprocess.SubprocessError, FileNotFoundError, Exception) as exc:
            logger.info(f"ffmpeg CLI unavailable or errored ({exc}). Attempting PyAV fallback.")
            pyav_ok = self._extract_with_pyav(input_path, output_path, sample_rate, channels)
            if pyav_ok:
                return True
            if input_path.lower().endswith(".wav"):
                try:
                    import wave
                    with wave.open(input_path, "rb") as wf:
                        if wf.getnframes() > 0:
                            shutil.copyfile(input_path, output_path)
                            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
                except Exception:
                    return False
            return False


_ffmpeg_service: Optional[FFmpegService] = None


def get_ffmpeg_service() -> FFmpegService:
    """Singleton getter for FFmpegService."""
    global _ffmpeg_service
    if _ffmpeg_service is None:
        _ffmpeg_service = FFmpegService()
    return _ffmpeg_service
