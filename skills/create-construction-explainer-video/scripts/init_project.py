#!/usr/bin/env python3
"""Initialize a construction-explainer video project without external dependencies."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


TRACKS = {
    "constructor-level-1": "一级建造师",
    "constructor-level-2": "二级建造师",
    "cost-engineer-level-1": "一级造价工程师",
}


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Output project directory")
    parser.add_argument("--exam-track", required=True, choices=sorted(TRACKS))
    parser.add_argument("--subject", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--specialty", default="建筑工程")
    parser.add_argument("--exam-year", type=int, default=datetime.now().year)
    parser.add_argument("--region", default="全国")
    parser.add_argument("--audience", default="备考入门用户")
    parser.add_argument("--force", action="store_true", help="Overwrite generated scaffold files")
    args = parser.parse_args()

    root = Path(args.project_dir).expanduser().resolve()
    marker = root / "project.json"
    if marker.exists() and not args.force:
        print(f"ERROR: {marker} already exists; use --force only for a disposable scaffold", file=sys.stderr)
        return 2

    now = datetime.now().astimezone().isoformat(timespec="seconds")
    for name in (
        "inputs",
        "research",
        "content",
        "audio",
        "images",
        "composition/vertical",
        "composition/landscape",
        "renders",
        "preview",
        "reports",
        "review",
    ):
        (root / name).mkdir(parents=True, exist_ok=True)

    project = {
        "schema_version": 1,
        "status": "draft",
        "created_at": now,
        "updated_at": now,
        "exam_track": args.exam_track,
        "exam_track_label": TRACKS[args.exam_track],
        "exam_year": args.exam_year,
        "region": args.region,
        "subject": args.subject,
        "specialty": args.specialty,
        "topic": args.topic,
        "audience": args.audience,
        "source_cutoff": now[:10],
        "duration_seconds": "auto",
        "duration_target_seconds": 90,
        "platforms": ["视频号", "抖音", "小红书", "B站", "课程平台"],
        "aspect_profiles": {
            "vertical": {"width": 1080, "height": 1920},
            "landscape": {"width": 1920, "height": 1080},
        },
        "brand": {"working_name": "建知课", "preset": "default"},
        "providers": {
            "tts": {"provider": "minimax-official", "model": "speech-2.8-hd"},
            "image_primary": {"provider": "dashscope", "model": "qwen-image-3.0-pro"},
            "image_fallback": {"provider": "agent-builtin-imagegen", "alt": {"provider": "openai", "model": "gpt-image-1"}},
        },
    }
    rights = {
        "materials": [],
        "defaults": {
            "allow_internal_research": True,
            "allow_third_party_processing": True,
            "allow_public_quote": False,
            "allow_public_image_reuse": False,
        },
        "notes": "Add one record per textbook, handout, question bank, standard or internal file.",
    }
    sources = {"source_cutoff": now[:10], "sources": []}
    evidence = {"claims": []}
    storyboard = {
        "topic": args.topic,
        "lesson_type": "construction-process",
        "voice": {
            "provider": "minimax-official",
            "model": "speech-2.8-hd",
            "voice_id": "female-chengshu",
            "speed": 1.0,
            "pronunciation_dict": {"tone": []},
        },
        "segments": [],
    }
    review = {
        "status": "pending",
        "reviewer": "",
        "role": "专业审核人",
        "reviewed_at": "",
        "version": "",
        "notes": "",
    }

    write_json(marker, project)
    write_json(root / "inputs/rights.json", rights)
    write_json(root / "research/sources.json", sources)
    write_json(root / "research/evidence.json", evidence)
    write_json(root / "content/storyboard.json", storyboard)
    write_json(root / "review/review.json", review)
    (root / "research/conflicts.md").write_text(
        "# 来源冲突与未决事项\n\n当前无记录。发现冲突时不要删除本文件中的历史记录。\n",
        encoding="utf-8",
    )

    print(f"Initialized: {root}")
    print("Next: populate research/sources.json, research/evidence.json, and content/storyboard.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
