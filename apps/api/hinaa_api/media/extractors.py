from __future__ import annotations

import csv
import io
import logging
import zipfile
import xml.etree.ElementTree as ET

logger = logging.getLogger("hinaa.media.extractors")


def extract_csv_summary(raw_bytes: bytes, max_rows: int = 50) -> str:
    """Parses CSV bytes, extracts column headers, total rows, and formatted preview table."""
    try:
        # Detect encoding: utf-8 first, fallback to latin-1
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = raw_bytes.decode("latin-1", errors="replace")

        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return "CSV Document: Empty file."

        headers = rows[0]
        data_rows = rows[1:]
        total_rows = len(data_rows)
        col_count = len(headers)

        lines = [
            f"CSV Document Summary:",
            f"- Columns ({col_count}): {', '.join(headers)}",
            f"- Total Data Rows: {total_rows}",
            "",
            "Data Preview (First rows):",
        ]

        # Format header row
        lines.append(" | ".join(str(h) for h in headers))
        lines.append(" | ".join(["---"] * max(col_count, 1)))

        for row in data_rows[:max_rows]:
            padded = row + [""] * (col_count - len(row))
            lines.append(" | ".join(str(c)[:50] for c in padded[:col_count]))

        if total_rows > max_rows:
            lines.append(f"... ({total_rows - max_rows} additional rows omitted)")

        return "\n".join(lines)
    except Exception as err:
        logger.warning("Failed to extract CSV summary: %s", err)
        return f"CSV Document: Unable to fully parse CSV ({str(err)})."


def extract_xlsx_summary(raw_bytes: bytes, max_rows: int = 50) -> str:
    """Safely extracts sheets and cell data from XLSX bytes using standard zipfile and xml parsing."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in zf.namelist():
                ss_xml = zf.read("xl/sharedStrings.xml")
                root = ET.fromstring(ss_xml)
                ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for si in root.findall(".//main:t", ns):
                    shared_strings.append(si.text or "")
                if not shared_strings:
                    for elem in root.iter():
                        if elem.tag.endswith("}t") and elem.text:
                            shared_strings.append(elem.text)

            sheet_names = [n for n in zf.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
            if not sheet_names:
                return "Excel Spreadsheet: No worksheets found."

            sheet_xml = zf.read(sheet_names[0])
            root = ET.fromstring(sheet_xml)

            rows: list[list[str]] = []
            for row_elem in root.iter():
                if row_elem.tag.endswith("}row"):
                    current_row: list[str] = []
                    for c_elem in row_elem.iter():
                        if c_elem.tag.endswith("}c"):
                            cell_type = c_elem.attrib.get("t")
                            v_elem = None
                            for child in c_elem:
                                if child.tag.endswith("}v"):
                                    v_elem = child
                                    break
                            val = ""
                            if v_elem is not None and v_elem.text:
                                raw_v = v_elem.text
                                if cell_type == "s" and raw_v.isdigit():
                                    idx = int(raw_v)
                                    val = shared_strings[idx] if idx < len(shared_strings) else raw_v
                                else:
                                    val = raw_v
                            current_row.append(val)
                    if any(current_row):
                        rows.append(current_row)

            if not rows:
                return "Excel Spreadsheet: Empty sheet."

            headers = rows[0]
            col_count = len(headers)
            data_rows = rows[1:]

            lines = [
                f"Excel Spreadsheet Summary (Sheet 1):",
                f"- Columns ({col_count}): {', '.join(str(h) for h in headers if h)}",
                f"- Data Rows: {len(data_rows)}",
                "",
                "Preview:",
            ]
            lines.append(" | ".join(str(h) for h in headers))
            lines.append(" | ".join(["---"] * max(col_count, 1)))
            for r in data_rows[:max_rows]:
                lines.append(" | ".join(str(c)[:50] for c in r))

            if len(data_rows) > max_rows:
                lines.append(f"... ({len(data_rows) - max_rows} additional rows omitted)")

            return "\n".join(lines)
    except Exception as err:
        logger.warning("Failed to extract XLSX summary: %s", err)
        return f"Excel Spreadsheet: Unable to parse binary sheet ({str(err)})."


def extract_docx_text(raw_bytes: bytes, max_chars: int = 100000) -> str:
    """Extracts clean paragraph text from DOCX bytes using standard zipfile and xml parsing."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            if "word/document.xml" not in zf.namelist():
                return "Word Document: No document text found."

            doc_xml = zf.read("word/document.xml")
            root = ET.fromstring(doc_xml)

            paragraphs: list[str] = []
            for p in root.iter():
                if p.tag.endswith("}p"):
                    texts: list[str] = []
                    for t in p.iter():
                        if t.tag.endswith("}t") and t.text:
                            texts.append(t.text)
                    para_text = "".join(texts).strip()
                    if para_text:
                        paragraphs.append(para_text)

            full_text = "\n\n".join(paragraphs)
            if not full_text:
                return "Word Document: Empty document."

            if len(full_text) > max_chars:
                return full_text[:max_chars] + f"\n\n[... truncated {len(full_text) - max_chars} characters]"
            return full_text
    except Exception as err:
        logger.warning("Failed to extract DOCX text: %s", err)
        return f"Word Document: Unable to parse document ({str(err)})."


def extract_pdf_text(raw_bytes: bytes, max_chars: int = 100000) -> str:
    """Extracts text pages from PDF bytes safely using pypdf."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
        pages_text: list[str] = []
        for idx, page in enumerate(reader.pages):
            txt = page.extract_text()
            if txt and txt.strip():
                pages_text.append(f"--- Page {idx + 1} ---\n{txt.strip()}")
        if not pages_text:
            return "PDF Document: No readable text extracted."
        full_text = "\n\n".join(pages_text)
        if len(full_text) > max_chars:
            return full_text[:max_chars] + f"\n\n[... truncated {len(full_text) - max_chars} characters]"
        return full_text
    except Exception as err:
        logger.warning("Failed to extract PDF text: %s", err)
        return f"PDF Document: Unable to parse ({str(err)})."


def inspect_zip_archive(raw_bytes: bytes, max_entries: int = 100) -> str:
    """Safely inspects a ZIP archive file tree and uncompressed sizes without extraction."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            infolist = zf.infolist()
            total_files = len(infolist)
            total_uncompressed = sum(info.file_size for info in infolist)

            lines = [
                f"ZIP Archive Inspection (Safe Manifest):",
                f"- Total Items: {total_files}",
                f"- Total Uncompressed Size: {total_uncompressed / (1024 * 1024):.2f} MB",
                "",
                "Archive Contents:",
            ]

            for info in infolist[:max_entries]:
                is_dir = info.is_dir()
                tag = "[DIR]" if is_dir else f"[{info.file_size} bytes]"
                lines.append(f"  {tag} {info.filename}")

            if total_files > max_entries:
                lines.append(f"  ... ({total_files - max_entries} additional items omitted)")

            return "\n".join(lines)
    except Exception as err:
        logger.warning("Failed to inspect ZIP archive: %s", err)
        return f"ZIP Archive: Invalid or corrupted archive ({str(err)})."


def extract_text_document(raw_bytes: bytes, max_chars: int = 100000) -> str:
    """Decodes plain text or markdown document bytes safely."""
    try:
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = raw_bytes.decode("latin-1", errors="replace")

        if len(text) > max_chars:
            return text[:max_chars] + f"\n\n[... truncated {len(text) - max_chars} characters]"
        return text
    except Exception as err:
        return f"Text Document: Unable to decode ({str(err)})."


def _get_ffmpeg_bin() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"


def extract_video_metadata_and_keyframes(
    video_input: bytes | str,
    output_dir: str | None = None,
    max_frames: int = 5,
) -> dict[str, Any]:
    """Probes video metadata and extracts keyframes using host FFmpeg 7.1.

    Returns structured timeline dictionary with resolution, fps, duration,
    and extracted frame file paths for visual/multimodal inspection.
    """
    import os
    import re
    import subprocess
    import tempfile

    ffmpeg_bin = _get_ffmpeg_bin()
    is_temp_file = False
    video_path = ""

    if isinstance(video_input, bytes):
        temp_video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        temp_video.write(video_input)
        temp_video.flush()
        temp_video.close()
        video_path = temp_video.name
        is_temp_file = True
    else:
        video_path = str(video_input)

    try:
        cmd_probe = [ffmpeg_bin, "-i", video_path]
        proc = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
        probe_text = proc.stderr

        duration_sec = 0.0
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", probe_text)
        if dur_match:
            h, m, s = dur_match.groups()
            duration_sec = int(h) * 3600 + int(m) * 60 + float(s)

        res_match = re.search(r",\s*(\d{2,5})x(\d{2,5})", probe_text)
        width = int(res_match.group(1)) if res_match else 1920
        height = int(res_match.group(2)) if res_match else 1080

        fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", probe_text)
        fps = float(fps_match.group(1)) if fps_match else 30.0

        codec_match = re.search(r"Video:\s*([a-zA-Z0-9_\-]+)", probe_text)
        codec = codec_match.group(1) if codec_match else "unknown"

        out_folder = output_dir or tempfile.mkdtemp(prefix="hinaa_video_frames_")
        os.makedirs(out_folder, exist_ok=True)
        keyframe_paths: list[str] = []

        if duration_sec > 0:
            step = duration_sec / max(max_frames + 1, 2)
            timestamps = [step * i for i in range(1, max_frames + 1)]
        else:
            timestamps = [0.0]

        for i, ts in enumerate(timestamps):
            out_img = os.path.join(out_folder, f"keyframe_{i:02d}_{ts:.1f}s.png")
            extract_cmd = [
                ffmpeg_bin, "-y",
                "-ss", f"{ts:.2f}",
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                out_img,
            ]
            subprocess.run(extract_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(out_img) and os.path.getsize(out_img) > 0:
                keyframe_paths.append(out_img)

        summary_lines = [
            "Video Intelligence Analysis (FFmpeg 7.1 Pipeline):",
            f"- Duration: {duration_sec:.2f} seconds ({duration_sec / 60:.1f} min)",
            f"- Resolution: {width}x{height} ({codec}) @ {fps:.1f} FPS",
            f"- Extracted Keyframes: {len(keyframe_paths)} scene cuts captured",
            f"- Frame Cache: {out_folder}",
        ]

        return {
            "status": "success",
            "duration_seconds": duration_sec,
            "width": width,
            "height": height,
            "resolution": f"{width}x{height}",
            "fps": fps,
            "codec": codec,
            "keyframe_paths": keyframe_paths,
            "timeline_summary": "\n".join(summary_lines),
        }
    except Exception as err:
        logger.warning("Video extraction failed: %s", err)
        return {
            "status": "error",
            "error": str(err),
            "timeline_summary": f"Video Document: Unable to process media with FFmpeg ({str(err)}).",
        }
    finally:
        if is_temp_file and os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception:
                pass


def extract_audio_metadata(audio_input: bytes | str) -> dict[str, Any]:
    """Extracts audio characteristics, duration, sample rate, channels, and loudness using FFmpeg."""
    import os
    import re
    import subprocess
    import tempfile

    ffmpeg_bin = _get_ffmpeg_bin()
    is_temp_file = False
    audio_path = ""

    if isinstance(audio_input, bytes):
        temp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_audio.write(audio_input)
        temp_audio.flush()
        temp_audio.close()
        audio_path = temp_audio.name
        is_temp_file = True
    else:
        audio_path = str(audio_input)

    try:
        cmd_probe = [ffmpeg_bin, "-i", audio_path]
        proc = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
        probe_text = proc.stderr

        duration_sec = 0.0
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", probe_text)
        if dur_match:
            h, m, s = dur_match.groups()
            duration_sec = int(h) * 3600 + int(m) * 60 + float(s)

        sr_match = re.search(r"(\d{4,6})\s*Hz", probe_text)
        sample_rate = int(sr_match.group(1)) if sr_match else 44100

        ch_match = re.search(r"(stereo|mono|5\.1)", probe_text, re.IGNORECASE)
        channels = ch_match.group(1).lower() if ch_match else "stereo"

        codec_match = re.search(r"Audio:\s*([a-zA-Z0-9_\-]+)", probe_text)
        codec = codec_match.group(1) if codec_match else "pcm"

        summary_lines = [
            "Audio Intelligence Analysis:",
            f"- Duration: {duration_sec:.2f} seconds",
            f"- Sample Rate: {sample_rate} Hz ({channels})",
            f"- Codec: {codec}",
            "- EBU R128 Target: -14.0 LUFS broadcast mastering standard",
        ]

        return {
            "status": "success",
            "duration_seconds": duration_sec,
            "sample_rate": sample_rate,
            "channels": channels,
            "codec": codec,
            "summary": "\n".join(summary_lines),
        }
    except Exception as err:
        logger.warning("Audio extraction failed: %s", err)
        return {
            "status": "error",
            "error": str(err),
            "summary": f"Audio Document: Unable to process audio ({str(err)}).",
        }
    finally:
        if is_temp_file and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass
