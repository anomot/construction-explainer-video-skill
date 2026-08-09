#!/usr/bin/env python3
"""Generate a non-critical illustration with DashScope qwen-image-3.0-pro."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


DEFAULT_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
SIZES = {"vertical": "1024*1536", "landscape": "1536*1024", "square": "1024*1024"}


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


def extract_image_url(body: dict) -> str:
    for choice in (body.get("output") or {}).get("choices", []):
        for item in ((choice.get("message") or {}).get("content") or []):
            if isinstance(item, dict) and item.get("image"):
                return str(item["image"])
    for item in (body.get("output") or {}).get("results", []):
        if isinstance(item, dict) and (item.get("url") or item.get("image")):
            return str(item.get("url") or item.get("image"))
    die("DashScope response does not contain an image URL")
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt")
    prompt_group.add_argument("--prompt-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--aspect", choices=sorted(SIZES), default="landscape")
    parser.add_argument("--model", default="qwen-image-3.0-pro")
    parser.add_argument("--endpoint", default=os.environ.get("DASHSCOPE_IMAGE_ENDPOINT", DEFAULT_ENDPOINT))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--no-prompt-extend", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_env_file(args.env_file)
    prompt = args.prompt if args.prompt is not None else args.prompt_file.read_text(encoding="utf-8").strip()
    if not prompt:
        die("prompt is empty")
    payload = {
        "model": args.model,
        "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
        "parameters": {"prompt_extend": not args.no_prompt_extend, "n": 1, "size": SIZES[args.aspect], "watermark": False},
    }
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("Dry run only; no API request sent")
        return 0

    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        die("DASHSCOPE_API_KEY is not set; pass --env-file or export it locally")
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    body: dict | None = None
    last_error: Exception | None = None
    for attempt in range(1, 4):
        request = urllib.request.Request(
            args.endpoint,
            data=encoded,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                body = json.loads(response.read().decode("utf-8"))
            if body.get("code"):
                raise RuntimeError(f"{body.get('code')}: {body.get('message', 'unknown error')}")
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            if 400 <= exc.code < 500 and exc.code != 429:
                die(f"DashScope HTTP {exc.code}: {detail}")
            last_error = RuntimeError(f"HTTP {exc.code}: {detail}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
        if attempt < 3:
            time.sleep(attempt * 3)
    if body is None:
        die(f"DashScope image generation failed: {last_error}")

    image_url = extract_image_url(body)
    if not image_url.startswith("https://"):
        die("provider returned a non-HTTPS image URL")
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(image_url, timeout=120) as response:
            content = response.read()
    except urllib.error.URLError as exc:
        die(f"failed to download generated image: {exc}")
    output.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    metadata = {
        "provider": "dashscope",
        "model": args.model,
        "aspect": args.aspect,
        "size_requested": SIZES[args.aspect],
        "prompt": prompt,
        "request_id": body.get("request_id"),
        "usage": body.get("usage"),
        "sha256": digest,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "knowledge_carrier": False,
    }
    output.with_suffix(output.suffix + ".json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Generated: {output}")
    print(f"SHA256: {digest}")
    print("Required next step: visually inspect the image; do not use it as technical evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
