"""Video/audio container & stream analysis via ffprobe (+ exiftool tags)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.models.schemas import Capability, ExtractionStatus, MetadataField, MetadataSection
from app.parsers.base import BaseParser, register
from app.security.subprocess_exec import ExternalToolError, run_tool
from app.services import exiftool_service
from app.services.exiftool_service import EXIFTOOL_AVAILABLE

FFPROBE_AVAILABLE = shutil.which("ffprobe") is not None

VIDEO_EXTS = {"mp4", "mov", "mkv", "avi", "webm", "mpeg", "mpg", "m4v"}
AUDIO_EXTS = {"mp3", "wav", "flac", "aac", "ogg", "oga", "m4a"}
MEDIA_FORMATS = {"MP4/MOV (ISO-BMFF)", "Matroska/WebM", "RIFF (WEBP/WAV/AVI)", "MP3 (ID3 tag)", "MP3 (MPEG audio)", "FLAC", "OGG"}


def _ffprobe_json(path: Path) -> dict:
    result = run_tool([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", "-show_chapters", str(path),
    ])
    if result.returncode != 0:
        raise ExternalToolError(result.stderr_text[:500] or "ffprobe failed")
    return json.loads(result.stdout_text or "{}")


class MediaParser(BaseParser):
    name = "media"

    def supports(self, detected_format: str, mime_type: str, extension: str) -> bool:
        return (
            detected_format in MEDIA_FORMATS
            or mime_type.startswith(("video/", "audio/"))
            or extension in VIDEO_EXTS
            or extension in AUDIO_EXTS
        )

    def get_capabilities(self, path: Path) -> list[Capability]:
        return [
            Capability(name="Container/stream analysis (ffprobe)", available=FFPROBE_AVAILABLE,
                       reason=None if FFPROBE_AVAILABLE else "ffprobe not installed"),
            Capability(name="Container tag editing", available=EXIFTOOL_AVAILABLE,
                       reason=None if EXIFTOOL_AVAILABLE else "exiftool not installed"),
            Capability(name="Frame-by-frame decoding", available=False, reason="Not performed — only container/stream metadata is analyzed."),
        ]

    def extract_metadata(self, path: Path) -> list[MetadataSection]:
        container = MetadataSection(section_id="media_container", title="Container Format", status=ExtractionStatus.NOT_ANALYZED)
        video_streams = MetadataSection(section_id="media_video_streams", title="Video Streams", status=ExtractionStatus.NOT_ANALYZED)
        audio_streams = MetadataSection(section_id="media_audio_streams", title="Audio Streams", status=ExtractionStatus.NOT_ANALYZED)
        other_streams = MetadataSection(section_id="media_other_streams", title="Subtitle / Chapters / Attachments", status=ExtractionStatus.NOT_ANALYZED)
        tags_section = MetadataSection(section_id="media_tags", title="Container Tags (Title/Author/Encoder)", status=ExtractionStatus.NOT_ANALYZED)

        if not FFPROBE_AVAILABLE:
            msg = "ffprobe is not installed; install FFmpeg to analyze media containers and streams."
            for s in (container, video_streams, audio_streams, other_streams):
                s.status = ExtractionStatus.NOT_ANALYZED
                s.detail_message = msg
        else:
            try:
                data = _ffprobe_json(path)
            except Exception as exc:
                for s in (container, video_streams, audio_streams, other_streams):
                    s.status = ExtractionStatus.FAILED
                    s.detail_message = str(exc)
                data = {}

            fmt = data.get("format", {})
            if fmt:
                fields = []
                for k, label in (
                    ("format_name", "Format Name"), ("format_long_name", "Format (Long)"),
                    ("duration", "Duration (s)"), ("size", "Size (bytes)"),
                    ("bit_rate", "Overall Bitrate (bps)"), ("nb_streams", "Stream Count"),
                    ("start_time", "Start Time (s)"),
                ):
                    if k in fmt:
                        fields.append(MetadataField(key=f"format:{k}", group="Container", label=label,
                                                      raw_value=fmt[k], normalized_value=fmt[k],
                                                      value_type="number" if k in ("duration", "size", "bit_rate", "nb_streams", "start_time") else "string",
                                                      source_parser="ffprobe"))
                container.fields = fields
                container.status = ExtractionStatus.SUCCESS if fields else ExtractionStatus.NO_METADATA

                tags = fmt.get("tags", {})
                if tags:
                    tags_section.fields = [
                        MetadataField(key=f"format_tag:{k}", group="Tags", label=k, raw_value=v, normalized_value=v,
                                      value_type="string", source_parser="ffprobe", writable=EXIFTOOL_AVAILABLE)
                        for k, v in tags.items()
                    ]
                    tags_section.status = ExtractionStatus.SUCCESS
                else:
                    tags_section.status = ExtractionStatus.NO_METADATA
            elif container.status == ExtractionStatus.NOT_ANALYZED:
                container.status = ExtractionStatus.NO_METADATA

            v_fields_present = False
            a_fields_present = False
            other_present = False
            for idx, stream in enumerate(data.get("streams", [])):
                codec_type = stream.get("codec_type")
                prefix = f"stream{idx}"
                common = [
                    ("codec_name", "Codec"), ("codec_long_name", "Codec (Long)"), ("profile", "Profile"),
                    ("codec_tag_string", "Codec Tag"), ("duration", "Duration (s)"), ("bit_rate", "Bitrate (bps)"),
                    ("start_time", "Start Time (s)"), ("nb_frames", "Frame Count (reported)"),
                ]
                if codec_type == "video":
                    specific = common + [
                        ("width", "Width"), ("height", "Height"), ("coded_width", "Coded Width"),
                        ("coded_height", "Coded Height"), ("pix_fmt", "Pixel Format"),
                        ("r_frame_rate", "Frame Rate (r)"), ("avg_frame_rate", "Frame Rate (avg)"),
                        ("display_aspect_ratio", "Display Aspect Ratio"), ("sample_aspect_ratio", "Sample Aspect Ratio"),
                        ("color_space", "Color Space"), ("color_range", "Color Range"), ("level", "Level"),
                    ]
                    rotate = stream.get("tags", {}).get("rotate")
                    fields = [MetadataField(key=f"{prefix}:{k}", group="Video Stream", label=f"[{idx}] {label}",
                                             raw_value=stream[k], normalized_value=stream[k], value_type="string",
                                             source_parser="ffprobe")
                              for k, label in specific if k in stream]
                    if rotate:
                        fields.append(MetadataField(key=f"{prefix}:rotate", group="Video Stream", label=f"[{idx}] Rotation",
                                                      raw_value=rotate, normalized_value=rotate, value_type="string", source_parser="ffprobe"))
                    video_streams.fields.extend(fields)
                    v_fields_present = v_fields_present or bool(fields)
                elif codec_type == "audio":
                    specific = common + [
                        ("sample_rate", "Sample Rate (Hz)"), ("channels", "Channels"),
                        ("channel_layout", "Channel Layout"), ("bits_per_sample", "Bit Depth"),
                        ("bits_per_raw_sample", "Bit Depth (raw)"),
                    ]
                    fields = [MetadataField(key=f"{prefix}:{k}", group="Audio Stream", label=f"[{idx}] {label}",
                                             raw_value=stream[k], normalized_value=stream[k], value_type="string",
                                             source_parser="ffprobe")
                              for k, label in specific if k in stream]
                    audio_streams.fields.extend(fields)
                    a_fields_present = a_fields_present or bool(fields)
                else:
                    fields = [MetadataField(key=f"{prefix}:{k}", group=codec_type or "Other Stream",
                                             label=f"[{idx}] {k}", raw_value=stream[k], normalized_value=stream[k],
                                             value_type="string", source_parser="ffprobe")
                              for k in ("codec_name", "codec_type", "codec_tag_string") if k in stream]
                    other_streams.fields.extend(fields)
                    other_present = other_present or bool(fields)

            for chapter in data.get("chapters", []):
                other_streams.fields.append(MetadataField(
                    key=f"chapter:{chapter.get('id')}", group="Chapters",
                    label=f"Chapter {chapter.get('id')}: {chapter.get('tags', {}).get('title', '')}",
                    raw_value=chapter, normalized_value=chapter, value_type="object", source_parser="ffprobe"))
                other_present = True

            video_streams.status = ExtractionStatus.SUCCESS if v_fields_present else (ExtractionStatus.NO_METADATA if FFPROBE_AVAILABLE and container.status != ExtractionStatus.FAILED else video_streams.status)
            audio_streams.status = ExtractionStatus.SUCCESS if a_fields_present else (ExtractionStatus.NO_METADATA if FFPROBE_AVAILABLE and container.status != ExtractionStatus.FAILED else audio_streams.status)
            other_streams.status = ExtractionStatus.SUCCESS if other_present else (ExtractionStatus.NO_METADATA if FFPROBE_AVAILABLE and container.status != ExtractionStatus.FAILED else other_streams.status)

        container.warnings.append("Frame counts are as reported by the container/stream index, not verified by decoding every frame.")
        return [container, video_streams, audio_streams, other_streams, tags_section]


register(MediaParser())
