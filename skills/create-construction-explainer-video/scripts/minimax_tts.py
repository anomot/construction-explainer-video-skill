#!/usr/bin/env python3
"""Generate segmented MiniMax TTS audio and an audio-driven timeline."""

from __future__ import annotations

import argparse
import binascii
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


HEAD_PAD = 0.65
TAIL_PAD = 0.9
DEFAULT_MIN_DURATION = 5.5
DEFAULT_VOICE = "female-chengshu"
DEFAULT_MODEL = "speech-2.8-hd"
NON_RETRYABLE_CODES = {1002, 1004, 1008, 2013}


def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_env_file(path: Path | None) -> None:
    if path is None:
        return
    if not path.exists():
        die(f"env file not found: {path}")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


def request_minimax(
    text: str,
    output: Path,
    voice_id: str,
    speed: float,
    model: str,
    pronunciation: dict,
) -> None:
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        die("MINIMAX_API_KEY is not set; pass --env-file or export it locally")
    host = os.environ.get("MINIMAX_API_HOST", "https://api.minimaxi.com").rstrip("/")
    url = f"{host}/v1/t2a_v2"
    group_id = os.environ.get("MINIMAX_GROUP_ID")
    if group_id:
        url += f"?GroupId={group_id}"

    payload = {
        "model": model,
        "text": text,
        "stream": False,
        "language_boost": "Chinese",
        "output_format": "hex",
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
            "vol": 1.0,
            "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
        "subtitle_enable": False,
    }
    if pronunciation.get("tone"):
        payload["pronunciation_dict"] = {"tone": pronunciation["tone"]}

    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(1, 4):
        req = urllib.request.Request(
            url,
            data=encoded,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                body = json.loads(response.read().decode("utf-8"))
            base = body.get("base_resp") or {}
            status = base.get("status_code")
            if status != 0:
                message = base.get("status_msg", "unknown MiniMax error")
                if status in NON_RETRYABLE_CODES or "balance" in message.lower():
                    die(f"MiniMax rejected request: status_code={status}, {message}")
                raise RuntimeError(f"status_code={status}, {message}")
            audio_hex = (body.get("data") or {}).get("audio")
            if not audio_hex:
                raise RuntimeError("response is missing data.audio")
            try:
                output.write_bytes(binascii.unhexlify(audio_hex))
            except (binascii.Error, ValueError) as exc:
                raise RuntimeError(f"invalid hexadecimal audio: {exc}") from exc
            return
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            if 400 <= exc.code < 500 and exc.code != 429:
                die(f"MiniMax HTTP {exc.code}: {detail}")
            last_error = RuntimeError(f"HTTP {exc.code}: {detail}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
        if attempt < 3:
            wait = attempt * 2
            print(f"WARN: TTS attempt {attempt} failed: {last_error}; retrying in {wait}s", flush=True)
            time.sleep(wait)
    die(f"MiniMax TTS failed after 3 attempts: {last_error}")


def request_say(text: str, output: Path, voice_id: str, speed: float, *_: object) -> None:
    if not shutil.which("say") or not shutil.which("ffmpeg"):
        die("macOS say and ffmpeg are required for preview fallback")
    voice = voice_id if voice_id and not voice_id.startswith(("female-", "male-", "presenter")) else "Tingting"
    aiff = output.with_suffix(".aiff")
    subprocess.run(["say", "-v", voice, "-r", str(int(180 * speed)), "-o", str(aiff), text], check=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), "-ar", "32000", "-b:a", "128k", str(output)],
        check=True,
    )
    aiff.unlink(missing_ok=True)


def duration_seconds(path: Path) -> float:
    if not shutil.which("ffprobe"):
        die("ffprobe is required to build the audio-driven timeline")
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        duration = float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as exc:
        die(f"generated audio is invalid or empty: {path}; local say preview may require normal macOS app permissions ({exc})")
    if duration <= 0:
        die(f"generated audio has non-positive duration: {path}")
    return duration


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboard")
    parser.add_argument("--outdir", default="audio")
    parser.add_argument("--provider", choices=("minimax", "say"), default=None)
    parser.add_argument("--voice")
    parser.add_argument("--speed", type=float)
    parser.add_argument("--model")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_env_file(args.env_file)
    source = Path(args.storyboard).expanduser().resolve()
    if not source.exists():
        die(f"storyboard not found: {source}")
    storyboard = json.loads(source.read_text(encoding="utf-8"))
    segments = storyboard.get("segments", [])
    if not 5 <= len(segments) <= 9:
        die(f"storyboard must contain 5-9 segments, got {len(segments)}")
    ids = [segment.get("id") for segment in segments]
    if ids != list(range(1, len(segments) + 1)):
        die(f"segment IDs must be continuous from 1: {ids}")

    config = storyboard.get("voice", {})
    provider = args.provider or ("minimax" if config.get("provider") != "say" else "say")
    voice_id = args.voice or config.get("voice_id") or DEFAULT_VOICE
    speed = args.speed if args.speed is not None else float(config.get("speed", 1.0))
    model = args.model or config.get("model") or os.environ.get("MINIMAX_TTS_MODEL", DEFAULT_MODEL)
    pronunciation = config.get("pronunciation_dict") or {"tone": []}
    if not 0.5 <= speed <= 2.0:
        die("speed must be between 0.5 and 2.0")

    print(f"TTS configuration: provider={provider}, model={model}, voice={voice_id}, speed={speed}")
    if args.dry_run:
        print(f"Dry run passed for {len(segments)} segments; no API request sent")
        return 0

    output_dir = Path(args.outdir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    engine = request_minimax if provider == "minimax" else request_say
    cursor = 0.0
    timeline: list[dict] = []
    for segment in segments:
        sid = int(segment["id"])
        text = str(segment.get("narration", "")).strip()
        if not text:
            die(f"segment {sid} has empty narration")
        output = output_dir / f"seg-{sid:02d}.mp3"
        print(f"[{sid}/{len(segments)}] {segment.get('title', '')} ({len(text)} chars)", flush=True)
        engine(text, output, voice_id, speed, model, pronunciation)
        audio_duration = round(duration_seconds(output), 3)
        minimum = float(segment.get("min_duration", DEFAULT_MIN_DURATION))
        scene_duration = round(max(HEAD_PAD + audio_duration + TAIL_PAD, minimum), 3)
        timeline.append(
            {
                "id": sid,
                "title": segment.get("title", ""),
                "file": f"audio/{output.name}",
                "audio_duration": audio_duration,
                "start": round(cursor, 3),
                "audio_start": round(cursor + HEAD_PAD, 3),
                "duration": scene_duration,
                "subtitle": text,
            }
        )
        cursor += scene_duration

    manifest = {
        "topic": storyboard.get("topic", ""),
        "provider": "minimax-official" if provider == "minimax" else "macos-say-preview",
        "model": model,
        "voice_id": voice_id,
        "head_pad": HEAD_PAD,
        "tail_pad": TAIL_PAD,
        "total": round(cursor, 3),
        "segments": timeline,
    }
    manifest_path = output_dir / "durations.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(timeline)} audio segments; timeline total={manifest['total']}s")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
