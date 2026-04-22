"""Shared upload helpers for browser and MCP attachments."""

from __future__ import annotations

import mimetypes
import shutil
import uuid
from pathlib import Path

INLINE_IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg",
}

SAFE_UPLOAD_EXTS = INLINE_IMAGE_EXTS | {
    ".txt", ".md", ".pdf", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".csv", ".tsv", ".log", ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz",
    ".py", ".js", ".jsx", ".ts", ".tsx", ".php", ".rb", ".go", ".rs",
    ".java", ".kt", ".swift", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs",
    ".css", ".scss", ".html", ".htm", ".sh", ".bash", ".zsh", ".sql",
    ".env", ".lock", ".xml", ".docx", ".xlsx", ".pptx",
}


def get_upload_dir(config: dict | None) -> Path:
    raw_dir = "./uploads"
    if config and "images" in config:
        raw_dir = config["images"].get("upload_dir", raw_dir)
    upload_dir = Path(raw_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def classify_upload(filename: str, content_type: str = "") -> dict | None:
    ext = Path(filename).suffix.lower()
    if ext not in SAFE_UPLOAD_EXTS:
        return None

    guessed_type, _ = mimetypes.guess_type(filename)
    media_type = content_type or guessed_type or "application/octet-stream"
    kind = "image" if ext in INLINE_IMAGE_EXTS else "file"
    if kind == "image" and not media_type.startswith("image/"):
        media_type = guessed_type or "image/*"

    return {
        "ext": ext,
        "kind": kind,
        "media_type": media_type,
    }


def build_attachment(original_name: str, stored_name: str, info: dict, size: int) -> dict:
    return {
        "name": Path(original_name).name,
        "url": f"/uploads/{stored_name}",
        "kind": info["kind"],
        "media_type": info["media_type"],
        "size": size,
    }


def write_upload_bytes(filename: str, content: bytes, config: dict | None, *, content_type: str = "") -> dict:
    info = classify_upload(filename, content_type=content_type)
    if info is None:
        raise ValueError(Path(filename).suffix or "(no extension)")

    stored_name = f"{uuid.uuid4().hex[:12]}{info['ext']}"
    upload_dir = get_upload_dir(config)
    (upload_dir / stored_name).write_bytes(content)
    return build_attachment(filename, stored_name, info, len(content))


def copy_upload_file(src: Path, config: dict | None) -> dict:
    info = classify_upload(src.name)
    if info is None:
        raise ValueError(src.suffix or "(no extension)")

    stored_name = f"{uuid.uuid4().hex[:12]}{info['ext']}"
    upload_dir = get_upload_dir(config)
    dest = upload_dir / stored_name
    shutil.copy2(str(src), str(dest))
    size = dest.stat().st_size if dest.exists() else 0
    return build_attachment(src.name, stored_name, info, size)
