#!/usr/bin/env python3
"""Generate a non-critical illustration with the OpenAI Images API (gpt-image-1).

Fallback tier when neither DashScope nor an agent-builtin image tool is available.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from env_utils import load_env

DEFAULT_ENDPOINT = "https://api.openai.com/v1/images/generations"
SIZES = {"vertical": "1024x1536", "landscape": "1536x1024", "square": "1024x1024"}


def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def extract_image(body: dict) -> bytes:
    for item in body.get("data") or []:
        if isinstance(item, dict) and item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        if isinstance(item, dict) and item.get("url"):
            url = str(item["url"])
            if not url.startswith("https://"):
                die("provider returned a non-HTTPS image URL")
            with urllib.request.urlopen(url, timeout=120) as response:
                return response.read()
    die("OpenAI response does not contain image data")
    return b""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt")
    prompt_group.add_argument("--prompt-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--aspect", choices=sorted(SIZES), default="landscape")
    parser.add_argument("--model", default="gpt-image-1")
    parser.add_argument("--quality", choices=("low", "medium", "high"), default="medium")
    parser.add_argument("--endpoint", default=os.environ.get("OPENAI_IMAGE_ENDPOINT", DEFAULT_ENDPOINT))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_env(args.env_file)
    prompt = args.prompt if args.prompt is not None else args.prompt_file.read_text(encoding="utf-8").strip()
    if not prompt:
        die("prompt is empty")
    payload = {
        "model": args.model,
        "prompt": prompt,
        "n": 1,
        "size": SIZES[args.aspect],
        "quality": args.quality,
    }
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("Dry run only; no API request sent")
        return 0

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        die("OPENAI_API_KEY is not set; pass --env-file or export it locally")
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
            if body.get("error"):
                raise RuntimeError(str(body["error"]))
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            if 400 <= exc.code < 500 and exc.code != 429:
                die(f"OpenAI HTTP {exc.code}: {detail}")
            last_error = RuntimeError(f"HTTP {exc.code}: {detail}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
        if attempt < 3:
            time.sleep(attempt * 3)
    if body is None:
        die(f"OpenAI image generation failed: {last_error}")

    content = extract_image(body)
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    metadata = {
        "provider": "openai",
        "model": args.model,
        "aspect": args.aspect,
        "size_requested": SIZES[args.aspect],
        "quality": args.quality,
        "prompt": prompt,
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
