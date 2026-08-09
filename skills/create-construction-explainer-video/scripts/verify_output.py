#!/usr/bin/env python3
"""Verify rendered MP4 dimensions, streams, durations, and audio presence."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


EXPECTED = {"vertical": (1080, 1920), "landscape": (1920, 1080)}


def probe(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir")
    parser.add_argument("--allow-silent", action="store_true", help="Allow missing audio for a preview-only render")
    args = parser.parse_args()
    if not shutil.which("ffprobe"):
        print("ERROR: ffprobe is required", file=sys.stderr)
        return 1

    root = Path(args.project_dir).expanduser().resolve()
    errors: list[str] = []
    outputs: list[dict] = []
    for profile, expected in EXPECTED.items():
        matches = sorted((root / "renders").glob(f"*{profile}*.mp4"))
        if not matches:
            errors.append(f"missing {profile} MP4")
            continue
        path = matches[-1]
        try:
            data = probe(path)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            errors.append(f"ffprobe failed for {path.name}: {exc}")
            continue
        video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
        audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
        if not video:
            errors.append(f"{path.name} has no video stream")
            continue
        actual = (video.get("width"), video.get("height"))
        if actual != expected:
            errors.append(f"{path.name} is {actual}, expected {expected}")
        if not audio and not args.allow_silent:
            errors.append(f"{path.name} has no audio stream")
        duration = float((data.get("format") or {}).get("duration") or 0)
        if duration <= 0:
            errors.append(f"{path.name} has invalid duration")
        outputs.append(
            {
                "profile": profile,
                "path": str(path),
                "width": video.get("width"),
                "height": video.get("height"),
                "video_codec": video.get("codec_name"),
                "audio_codec": audio.get("codec_name") if audio else None,
                "duration": duration,
                "size_bytes": int((data.get("format") or {}).get("size") or 0),
            }
        )

    report = {
        "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "outputs": outputs,
    }
    report_path = root / "reports/output-verification.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Output verification: {report['status']}")
    for item in errors:
        print(f"ERROR: {item}")
    print(f"Report: {report_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
