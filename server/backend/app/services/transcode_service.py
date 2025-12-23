# Transcoding service - FFmpeg operations, quality presets, job management

import subprocess
import os
import json
import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Quality presets: resolution -> (width, height, video_bitrate, audio_bitrate)
QUALITY_PRESETS = {
    480: {"width": 854, "height": 480, "video_bitrate": "1000k", "audio_bitrate": "128k"},
    720: {"width": 1280, "height": 720, "video_bitrate": "2500k", "audio_bitrate": "192k"},
    1080: {"width": 1920, "height": 1080, "video_bitrate": "5000k", "audio_bitrate": "256k"},
}


class TranscodeService:
    """Service for video transcoding operations using FFmpeg"""

    def __init__(self):
        self.ffmpeg_path = self._find_ffmpeg()
        self.ffprobe_path = self._find_ffprobe()

    def _find_ffmpeg(self) -> str:
        """Find FFmpeg binary path"""
        # Check common locations
        for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "ffmpeg"]:
            try:
                result = subprocess.run([path, "-version"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    return path
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        raise RuntimeError("FFmpeg not found. Please install FFmpeg.")

    def _find_ffprobe(self) -> str:
        """Find FFprobe binary path"""
        for path in ["/usr/bin/ffprobe", "/usr/local/bin/ffprobe", "ffprobe"]:
            try:
                result = subprocess.run([path, "-version"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    return path
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        raise RuntimeError("FFprobe not found. Please install FFmpeg.")

    def get_video_info(self, input_path: str) -> Dict[str, Any]:
        """
        Get video metadata using FFprobe

        Returns:
            Dict with duration, width, height, codec, bitrate, fps
        """
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            input_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise RuntimeError(f"FFprobe failed: {result.stderr}")

            data = json.loads(result.stdout)

            # Find video stream
            video_stream = None
            audio_stream = None
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video" and not video_stream:
                    video_stream = stream
                elif stream.get("codec_type") == "audio" and not audio_stream:
                    audio_stream = stream

            if not video_stream:
                raise RuntimeError("No video stream found in file")

            format_info = data.get("format", {})

            # Calculate FPS from frame rate string (e.g., "30/1" or "29.97")
            fps_str = video_stream.get("r_frame_rate", "0/1")
            try:
                if "/" in fps_str:
                    num, den = fps_str.split("/")
                    fps = float(num) / float(den) if float(den) != 0 else 0
                else:
                    fps = float(fps_str)
            except (ValueError, ZeroDivisionError):
                fps = 0

            return {
                "duration": float(format_info.get("duration", 0)),
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "codec": video_stream.get("codec_name", "unknown"),
                "bitrate": int(format_info.get("bit_rate", 0)),
                "fps": round(fps, 2),
                "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
                "file_size": int(format_info.get("size", 0)),
            }

        except subprocess.TimeoutExpired:
            raise RuntimeError("FFprobe timed out")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse FFprobe output: {e}")

    def transcode(
        self,
        input_path: str,
        output_path: str,
        target_quality: int,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Transcode video to target quality

        Args:
            input_path: Path to input video file
            output_path: Path for output video file
            target_quality: Target quality (480, 720, 1080)
            progress_callback: Optional callback(progress_percent) for progress updates

        Returns:
            Dict with transcoding results (output_size, duration, etc.)
        """
        if target_quality not in QUALITY_PRESETS:
            raise ValueError(f"Invalid quality: {target_quality}. Must be one of {list(QUALITY_PRESETS.keys())}")

        preset = QUALITY_PRESETS[target_quality]

        # Get input video info for progress calculation
        video_info = self.get_video_info(input_path)
        total_duration = video_info["duration"]

        # Build FFmpeg command
        # Using libx264 for compatibility, hardware acceleration can be added later
        cmd = [
            self.ffmpeg_path,
            "-y",  # Overwrite output
            "-i", input_path,
            # Video settings
            "-c:v", "libx264",
            "-preset", "medium",  # Balance between speed and quality
            "-crf", "23",  # Constant Rate Factor (lower = better quality, 18-28 is good)
            "-vf", f"scale={preset['width']}:{preset['height']}:force_original_aspect_ratio=decrease,pad={preset['width']}:{preset['height']}:(ow-iw)/2:(oh-ih)/2",
            "-b:v", preset["video_bitrate"],
            "-maxrate", preset["video_bitrate"],
            "-bufsize", str(int(preset["video_bitrate"].replace("k", "")) * 2) + "k",
            # Audio settings
            "-c:a", "aac",
            "-b:a", preset["audio_bitrate"],
            "-ar", "44100",  # Sample rate
            # Output format
            "-movflags", "+faststart",  # Enable streaming
            "-f", "mp4",
            # Progress output
            "-progress", "pipe:1",
            "-nostats",
            output_path
        ]

        logger.info(f"Starting transcode: {input_path} -> {output_path} @ {target_quality}p")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Parse progress from FFmpeg output
            current_time = 0
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                if line.startswith("out_time_ms="):
                    try:
                        time_ms = int(line.split("=")[1].strip())
                        current_time = time_ms / 1_000_000  # Convert to seconds
                        if total_duration > 0 and progress_callback:
                            progress = min(100, (current_time / total_duration) * 100)
                            progress_callback(progress)
                    except (ValueError, IndexError):
                        pass

            # Wait for process to complete
            process.wait()

            if process.returncode != 0:
                stderr = process.stderr.read()
                raise RuntimeError(f"FFmpeg failed with code {process.returncode}: {stderr}")

            # Get output file info
            output_size = os.path.getsize(output_path)
            output_info = self.get_video_info(output_path)

            return {
                "success": True,
                "output_path": output_path,
                "output_size": output_size,
                "duration": output_info["duration"],
                "width": output_info["width"],
                "height": output_info["height"],
                "bitrate": output_info["bitrate"],
            }

        except subprocess.TimeoutExpired:
            process.kill()
            raise RuntimeError("FFmpeg transcoding timed out")

    def get_recommended_qualities(self, source_height: int) -> list:
        """
        Get recommended transcoding qualities based on source resolution

        Args:
            source_height: Height of source video in pixels

        Returns:
            List of recommended quality values (e.g., [480, 720])
        """
        qualities = []
        for quality in sorted(QUALITY_PRESETS.keys()):
            if quality < source_height:
                qualities.append(quality)
        return qualities


# Global service instance
transcode_service = TranscodeService()
