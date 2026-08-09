#!/usr/bin/env python3
"""Validate input, research, content, and publish gates for a video project."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


TRACKS = {"constructor-level-1", "constructor-level-2", "cost-engineer-level-1"}
STAGES = {"input": 0, "research": 1, "content": 2, "publish": 3}


def read_json(path: Path, errors: list[str]) -> dict:
    if not path.exists():
        errors.append(f"missing file: {path}")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid JSON: {path}: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"expected JSON object: {path}")
        return {}
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir")
    parser.add_argument("--stage", choices=STAGES, default="content")
    args = parser.parse_args()

    root = Path(args.project_dir).expanduser().resolve()
    target = STAGES[args.stage]
    errors: list[str] = []
    warnings: list[str] = []

    project = read_json(root / "project.json", errors)
    for field in ("exam_track", "exam_year", "region", "subject", "topic", "source_cutoff"):
        if not project.get(field):
            errors.append(f"project.json missing required field: {field}")
    if project.get("exam_track") not in TRACKS:
        errors.append(f"exam_track is outside MVP: {project.get('exam_track')!r}")
    if project.get("exam_track") == "constructor-level-2" and project.get("region") in (None, "", "全国"):
        warnings.append("二建项目使用全国口径；涉及地方政策时必须指定省市")
    aspects = project.get("aspect_profiles", {})
    for profile, expected in {"vertical": (1080, 1920), "landscape": (1920, 1080)}.items():
        cfg = aspects.get(profile, {})
        if (cfg.get("width"), cfg.get("height")) != expected:
            errors.append(f"{profile} must be {expected[0]}x{expected[1]}")

    claim_ids: set[str] = set()
    if target >= STAGES["research"]:
        sources_doc = read_json(root / "research/sources.json", errors)
        evidence_doc = read_json(root / "research/evidence.json", errors)
        rights_doc = read_json(root / "inputs/rights.json", errors)
        sources = sources_doc.get("sources", [])
        claims = evidence_doc.get("claims", [])
        if not sources:
            errors.append("research/sources.json has no sources")
        if not claims:
            errors.append("research/evidence.json has no claims")
        source_ids = {s.get("id") for s in sources if s.get("id")}
        if len(source_ids) != len([s for s in sources if s.get("id")]):
            errors.append("source IDs must be unique")
        rights_ids = {m.get("id") for m in rights_doc.get("materials", []) if m.get("id")}
        for source in sources:
            if source.get("type") == "user-material" and source.get("rights_id") not in rights_ids:
                errors.append(f"user material {source.get('id')} lacks a valid rights_id")
            if not source.get("title"):
                errors.append(f"source {source.get('id', '?')} lacks title")
        for claim in claims:
            cid = claim.get("id")
            if not cid:
                errors.append("claim lacks id")
                continue
            if cid in claim_ids:
                errors.append(f"duplicate claim id: {cid}")
            claim_ids.add(cid)
            if not claim.get("text"):
                errors.append(f"claim {cid} lacks text")
            if claim.get("verified") is not True:
                errors.append(f"claim {cid} is not verified")
            refs = claim.get("source_ids", [])
            if not refs:
                errors.append(f"claim {cid} has no source_ids")
            unknown = sorted(set(refs) - source_ids)
            if unknown:
                errors.append(f"claim {cid} references unknown sources: {unknown}")
            if claim.get("risk") not in {"low", "medium", "high"}:
                errors.append(f"claim {cid} has invalid risk")

    if target >= STAGES["content"]:
        storyboard = read_json(root / "content/storyboard.json", errors)
        segments = storyboard.get("segments", [])
        if not 5 <= len(segments) <= 9:
            errors.append(f"storyboard must contain 5-9 segments, got {len(segments)}")
        expected_ids = list(range(1, len(segments) + 1))
        actual_ids = [seg.get("id") for seg in segments]
        if actual_ids != expected_ids:
            errors.append(f"segment IDs must be continuous from 1: {actual_ids}")
        used_claims: set[str] = set()
        for seg in segments:
            sid = seg.get("id", "?")
            for field in ("title", "narration", "headline", "visual_type"):
                if not seg.get(field):
                    errors.append(f"segment {sid} missing {field}")
            refs = seg.get("claim_ids", [])
            if not refs:
                errors.append(f"segment {sid} has no claim_ids")
            unknown = sorted(set(refs) - claim_ids)
            if unknown:
                errors.append(f"segment {sid} references unknown claims: {unknown}")
            used_claims.update(refs)
            if len(seg.get("narration", "")) > 160:
                warnings.append(f"segment {sid} narration exceeds 160 Chinese characters")
        unused = sorted(claim_ids - used_claims)
        if unused:
            warnings.append(f"verified claims not used in storyboard: {unused}")
        voice = storyboard.get("voice", {})
        if voice.get("model") != "speech-2.8-hd":
            warnings.append("voice model differs from MVP default speech-2.8-hd")

    if target >= STAGES["publish"]:
        review = read_json(root / "review/review.json", errors)
        if review.get("status") != "approved":
            errors.append("human professional review is not approved")
        for field in ("reviewer", "role", "reviewed_at", "version"):
            if not review.get(field):
                errors.append(f"approved review missing {field}")
        renders = list((root / "renders").glob("*.mp4")) if (root / "renders").exists() else []
        if not any("vertical" in p.name for p in renders):
            errors.append("missing vertical MP4")
        if not any("landscape" in p.name for p in renders):
            errors.append("missing landscape MP4")
        output_report = root / "reports/output-verification.json"
        if not output_report.exists():
            errors.append("missing reports/output-verification.json")

    report = {
        "stage": args.stage,
        "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
    }
    report_path = root / "reports/validation-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Validation {args.stage}: {report['status']} ({len(errors)} errors, {len(warnings)} warnings)")
    for item in errors:
        print(f"ERROR: {item}")
    for item in warnings:
        print(f"WARN: {item}")
    print(f"Report: {report_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
