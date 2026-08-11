#!/usr/bin/env python3
"""Build deterministic HyperFrames HTML compositions for vertical and landscape video.

Key features:
- Beat scheduling: animation groups are distributed across each scene's real
  audio-driven duration instead of fixed offsets, so motion tracks narration.
- Continue mode: multi-step demos keep structural graphics static between
  scenes and only animate the newly discussed annotations.
- Sentence-level subtitles: narration is chunked and timed proportionally.
- Seven deterministic calculation components, all data-driven with hard
  failures when storyboard data is missing (no silent demo fallbacks).
"""

from __future__ import annotations

import argparse
import html
import json
import math
import shutil
import sys
from pathlib import Path

from env_utils import HEAD_PAD, TAIL_PAD, estimate_duration

PROFILES = {"vertical": (1080, 1920), "landscape": (1920, 1080)}
SKILL_ROOT = Path(__file__).resolve().parent.parent
GSAP_VENDOR = SKILL_ROOT / "assets/vendor/gsap.min.js"

# Storyboard data key required for each dynamic visual type (no silent defaults).
DYNAMIC_DATA_KEYS = {
    "network-plan": "network",
    "earthwork-volume": "geometry",
    "cashflow": "cashflow",
    "component-volume": "component_volume",
    "flow-schedule": "flow_schedule",
    "rebar-length": "rebar",
    "earned-value": "earned_value",
    "projection-point": "projection",
}

TRANSITIONS = {"hold", "blur-crossfade", "push-up", "push-left"}


def G(name: str, style: str, per: float = 0.03, with_prev: bool = False) -> dict:
    return {"name": name, "style": style, "per": per, "with_prev": with_prev}


# Ordered animation groups per visual type. Order == expected narration order.
GROUP_SPECS: dict[str, list[dict]] = {
    "concept": [
        G("concept-lines", "draw", 0.05),
        G("concept-arrow", "draw", 0.04, with_prev=True),
        G("concept-pulse", "pop"),
        G("concept-number", "pop"),
    ],
    "process": [G("step-items", "rise", 0.05)],
    "timeline": [G("step-items", "rise", 0.05)],
    "comparison": [
        G("cmp-left", "rise"),
        G("cmp-right", "rise"),
        G("cmp-points", "rise", 0.04),
    ],
    "calculation": [
        G("calc-formula", "pop"),
        G("calc-steps", "rise", 0.07),
        G("calc-result", "pop"),
    ],
    "summary": [G("sum-number", "pop"), G("sum-pills", "pop", 0.05)],
    "network-plan": [
        G("net-nodes", "pop", 0.03),
        G("net-edges", "draw", 0.045),
        G("net-heads", "fade", 0.045, with_prev=True),
        G("net-labels", "rise", 0.035),
        G("net-times", "pop", 0.05),
        G("net-late", "pop", 0.05),
        G("net-critical", "highlight", 0.04),
        G("net-metrics", "pop", 0.04),
    ],
    "earthwork-volume": [
        G("earth-section", "draw", 0.04),
        G("earth-cut", "grow-y", with_prev=True),
        G("earth-dims", "draw", 0.05),
        G("earth-dimlabels", "fade", 0.05, with_prev=True),
        G("earth-plans", "pop", 0.05),
        G("earth-plantexts", "rise", 0.04, with_prev=True),
        G("earth-steps", "rise", 0.06),
    ],
    "cashflow": [
        G("cash-axis", "draw"),
        G("cash-periods", "fade", 0.02, with_prev=True),
        G("cash-arrows", "grow-y", 0.04),
        G("cash-marks", "pop", 0.04, with_prev=True),
        G("cash-rate", "fade"),
        G("cash-discounts", "pop", 0.05),
        G("cash-result", "pop"),
    ],
    "component-volume": [
        G("vol-base", "draw"),
        G("vol-blocks", "pop", 0.06),
        G("vol-chips", "rise", 0.05),
        G("vol-total", "pop"),
    ],
    "flow-schedule": [
        G("flow-grid", "draw", 0.012),
        G("flow-times", "fade", 0.012, with_prev=True),
        G("flow-procs", "fade", 0.02, with_prev=True),
        G("flow-blocks", "grow-x", 0.022),
        G("flow-metrics", "rise", 0.03),
        G("flow-result", "pop"),
    ],
    "rebar-length": [
        G("rebar-path", "draw", 0.09),
        G("rebar-bends", "pop", 0.05, with_prev=True),
        G("rebar-dims", "fade", 0.05),
        G("rebar-bars", "grow-x", 0.06),
        G("rebar-result", "pop"),
    ],
    "earned-value": [
        G("ev-axes", "draw", 0.02),
        G("ev-legend", "fade", 0.02, with_prev=True),
        G("ev-pv", "draw"),
        G("ev-ev", "draw"),
        G("ev-ac", "draw"),
        G("ev-gaps", "pop", 0.05),
        G("ev-chips", "rise", 0.05),
    ],
    # Stage "system" emits planes/labels/point/rays/feet; stage "unfold" emits
    # planes/labels/arrows/rays/feet. Absent groups should be listed in the
    # scene's animation.static_groups so their anchor slots are not wasted.
    "projection-point": [
        G("proj-planes", "draw", 0.06),
        G("proj-labels", "fade", 0.05, with_prev=True),
        G("proj-point", "pop"),
        G("proj-arrows", "draw", 0.1),
        G("proj-rays", "fade", 0.08),
        G("proj-feet", "pop", 0.08),
        G("proj-result", "pop"),
    ],
}

# Structural groups that stay static when animation.mode == "continue".
DEFAULT_STATIC: dict[str, list[str]] = {
    "network-plan": ["net-nodes", "net-edges", "net-heads", "net-labels"],
    "earthwork-volume": ["earth-section", "earth-cut", "earth-dims", "earth-dimlabels"],
    "cashflow": ["cash-axis", "cash-periods", "cash-arrows", "cash-marks", "cash-rate"],
    "component-volume": ["vol-base", "vol-blocks"],
    "flow-schedule": ["flow-grid", "flow-times", "flow-procs"],
    "rebar-length": ["rebar-path", "rebar-bends", "rebar-dims"],
    "earned-value": ["ev-axes", "ev-legend", "ev-pv", "ev-ev", "ev-ac"],
    "projection-point": ["proj-planes", "proj-labels", "proj-point"],
}

ANCHOR_FIRST = 0.08
ANCHOR_LAST = 0.68


def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_json(path: Path) -> dict:
    if not path.exists():
        die(f"missing file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"invalid JSON: {path}: {exc}")
    if not isinstance(data, dict):
        die(f"expected JSON object: {path}")
    return data


def e(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def dynamic_data(segment: dict) -> dict:
    """Return the required data block for a dynamic visual type or die."""
    visual_type = segment.get("visual_type", "")
    key = DYNAMIC_DATA_KEYS[visual_type]
    data = segment.get(key)
    if not isinstance(data, dict) or not data:
        die(
            f"segment {segment.get('id', '?')} uses visual_type={visual_type!r} "
            f"but has no {key!r} data block; demo defaults are not allowed"
        )
    return data


def chunk_narration(text: str, max_chars: int = 34) -> list[str]:
    """Split narration into subtitle chunks at sentence and clause boundaries."""
    sentences: list[str] = []
    buffer = ""
    for char in text.strip():
        buffer += char
        if char in "。！？；":
            sentences.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        sentences.append(buffer.strip())

    chunks: list[str] = []
    for sentence in sentences:
        if len(sentence) <= max_chars:
            chunks.append(sentence)
            continue
        # Secondary split on commas, greedily merged up to max_chars.
        parts: list[str] = []
        piece = ""
        for char in sentence:
            piece += char
            if char in "，、" and len(piece) >= max_chars * 0.4:
                parts.append(piece)
                piece = ""
        if piece:
            parts.append(piece)
        merged = ""
        for part in parts:
            if merged and len(merged) + len(part) > max_chars:
                chunks.append(merged)
                merged = part
            else:
                merged += part
        if merged:
            chunks.append(merged)
    return [c for c in chunks if c]


def subtitle_windows(row: dict) -> list[dict]:
    """Time subtitle chunks proportionally inside the audio window."""
    text = str(row.get("subtitle", "")).strip()
    if not text:
        return []
    chunks = chunk_narration(text)
    total_chars = sum(len(c) for c in chunks) or 1
    audio_start = float(row["audio_start"])
    audio_duration = max(float(row["audio_duration"]), 0.8)
    scene_end = float(row["start"]) + float(row["duration"])
    subs = []
    cursor = audio_start
    for index, chunk in enumerate(chunks):
        share = len(chunk) / total_chars * audio_duration
        start = cursor
        end = cursor + share
        if index == len(chunks) - 1:
            end = min(end + TAIL_PAD * 0.6, scene_end - 0.15)
        subs.append({"text": chunk, "in": round(start, 3), "out": round(max(end, start + 0.8), 3)})
        cursor = end
    return subs


def schedule_groups(segment: dict) -> list[dict]:
    """Compute anchor fractions for every animated group of a segment."""
    visual_type = segment.get("visual_type", "concept")
    spec = GROUP_SPECS.get(visual_type, GROUP_SPECS["concept"])
    anim = segment.get("animation") or {}
    mode = anim.get("mode", "build")
    static = set(anim.get("static_groups") or (DEFAULT_STATIC.get(visual_type, []) if mode == "continue" else []))
    beats = {b.get("group"): b for b in anim.get("beats", []) if isinstance(b, dict) and b.get("group")}

    active = [dict(g) for g in spec if g["name"] not in static]
    main = [g for g in active if not g["with_prev"]]
    count = len(main)
    for index, group in enumerate(main):
        if count <= 1:
            group["at"] = 0.30
        else:
            group["at"] = round(ANCHOR_FIRST + (ANCHOR_LAST - ANCHOR_FIRST) * index / (count - 1), 4)
    previous_at = ANCHOR_FIRST
    for group in active:
        if group["with_prev"]:
            group["at"] = round(min(previous_at + 0.06, 0.85), 4)
        previous_at = group["at"]

    # Knowledge-card bullets are always animated, spread through the middle.
    bullet_count = len([b for b in segment.get("bullets", []) if str(b).strip()])
    if bullet_count:
        per = round(0.55 / max(bullet_count - 1, 1), 4) if bullet_count > 1 else 0.0
        active.append({"name": "card-bullets", "style": "rise", "per": min(per, 0.22), "at": 0.18})

    for group in active:
        beat = beats.get(group["name"])
        if beat:
            at = beat.get("at")
            if isinstance(at, (int, float)):
                group["at"] = round(min(max(float(at), 0.02), 0.9), 4)
            stagger = beat.get("stagger")
            if isinstance(stagger, (int, float)):
                group["per"] = round(min(max(float(stagger), 0.0), 0.5), 4)

    return [{"name": g["name"], "style": g["style"], "at": g["at"], "per": g["per"]} for g in active]


def estimated_timeline(segments: list[dict]) -> dict:
    cursor = 0.0
    rows = []
    for segment in segments:
        narration = str(segment.get("narration", ""))
        duration = estimate_duration(narration, float(segment.get("min_duration", 5.5)))
        rows.append(
            {
                "id": segment["id"],
                "title": segment.get("title", ""),
                "file": f"audio/seg-{int(segment['id']):02d}.mp3",
                "audio_duration": max(0.0, round(duration - HEAD_PAD - TAIL_PAD, 3)),
                "start": round(cursor, 3),
                "audio_start": round(cursor + HEAD_PAD, 3),
                "duration": duration,
                "subtitle": narration,
            }
        )
        cursor += duration
    return {"total": round(cursor, 3), "segments": rows, "preview_timing": True}


# ---------------------------------------------------------------------------
# Dynamic visual markup builders
# ---------------------------------------------------------------------------


def network_plan_markup(segment: dict) -> str:
    network = dynamic_data(segment)
    nodes = network.get("nodes")
    activities = network.get("activities")
    if not nodes or not activities:
        die(f"segment {segment.get('id', '?')} network data must include nodes and activities")
    by_id = {str(node.get("id")): node for node in nodes}
    edges = []
    labels = []
    for activity in activities:
        start = by_id.get(str(activity.get("from")))
        end = by_id.get(str(activity.get("to")))
        if not start or not end:
            die(f"segment {segment.get('id', '?')} activity references unknown node: {activity}")
        x1, y1 = float(start.get("x", 0)), float(start.get("y", 0))
        x2, y2 = float(end.get("x", 0)), float(end.get("y", 0))
        dx, dy = x2 - x1, y2 - y1
        distance = max(math.hypot(dx, dy), 1.0)
        ux, uy = dx / distance, dy / distance
        sx, sy = x1 + ux * 39, y1 + uy * 39
        ex, ey = x2 - ux * 45, y2 - uy * 45
        critical = " critical-activity" if activity.get("critical") else ""
        crit_attr = ' data-anim2="net-critical"' if activity.get("critical") else ""
        arrow_base_x, arrow_base_y = ex - ux * 18, ey - uy * 18
        px, py = -uy * 9, ux * 9
        edges.append(
            f'<path data-anim="net-edges"{crit_attr} class="draw network-activity{critical}" d="M {sx:.1f} {sy:.1f} L {ex:.1f} {ey:.1f}" />'
            f'<polygon data-anim="net-heads"{crit_attr} data-hl="fill" class="network-arrow{critical}" points="{ex:.1f},{ey:.1f} {arrow_base_x + px:.1f},{arrow_base_y + py:.1f} {arrow_base_x - px:.1f},{arrow_base_y - py:.1f}" />'
        )
        label = e(activity.get("label", ""))
        duration = e(activity.get("duration", ""))
        text = " · ".join(item for item in (label, f"{duration}天" if duration else "") if item)
        mx, my = (sx + ex) / 2, (sy + ey) / 2 - 14
        labels.append(
            f'<g data-anim="net-labels" class="network-label" transform="translate({mx:.1f} {my:.1f})"><rect x="-46" y="-21" width="92" height="34" rx="17"/><text text-anchor="middle" y="4">{text}</text></g>'
        )
    node_groups = []
    for node in nodes:
        node_id = e(node.get("id", ""))
        x, y = float(node.get("x", 0)), float(node.get("y", 0))
        early, late = node.get("early"), node.get("late")
        time_text = ""
        if early is not None:
            time_text += (
                f'<text data-anim="net-times" class="node-time node-time-early" text-anchor="end" x="-5" y="68">'
                f'早 {html.escape(str(early))}</text>'
            )
        if late is not None:
            time_text += (
                f'<text data-anim="net-late" class="node-time node-time-late" text-anchor="start" x="5" y="68">'
                f'迟 {html.escape(str(late))}</text>'
            )
        node_groups.append(
            f'<g class="network-node" transform="translate({x:.1f} {y:.1f})"><g data-anim="net-nodes" class="network-node-core"><circle r="36"/><text text-anchor="middle" y="10">{node_id}</text></g>{time_text}</g>'
        )
    metrics = network.get("metrics") or []
    metric_html = "".join(f'<span data-anim="net-metrics" class="metric-chip">{e(item)}</span>' for item in metrics[:4])
    return f'''<div class="network-visual">
      <svg viewBox="0 0 900 560" aria-label="双代号网络计划动态图">
        {''.join(edges)}
        {''.join(labels)}
        {''.join(node_groups)}
      </svg>
      <div class="metric-row">{metric_html}</div>
    </div>'''


def earthwork_markup(segment: dict) -> str:
    geometry = dynamic_data(segment)
    for field in ("bottom_length", "bottom_width", "depth", "slope"):
        if field not in geometry:
            die(f"segment {segment.get('id', '?')} geometry missing {field}")
    bottom_length = float(geometry["bottom_length"])
    bottom_width = float(geometry["bottom_width"])
    depth = float(geometry["depth"])
    slope = float(geometry["slope"])
    top_length = float(geometry.get("top_length", bottom_length + 2 * slope * depth))
    top_width = float(geometry.get("top_width", bottom_width + 2 * slope * depth))
    mid_length = (bottom_length + top_length) / 2
    mid_width = (bottom_width + top_width) / 2
    area_bottom = bottom_length * bottom_width
    area_mid = mid_length * mid_width
    area_top = top_length * top_width
    volume = depth / 6 * (area_bottom + 4 * area_mid + area_top)
    supplied_steps = segment.get("steps") or []
    formula_steps = supplied_steps[:4] or [
        f"顶口：{top_length:g} × {top_width:g} 米",
        f"中截面：{mid_length:g} × {mid_width:g} 米",
        f"三面积：{area_bottom:g}、{area_mid:g}、{area_top:g} 平方米",
        f"体积：{volume:g} 立方米",
    ]
    step_html = "".join(
        f'<div data-anim="earth-steps" class="formula-stage"><span>{index}</span>{e(item)}</div>'
        for index, item in enumerate(formula_steps, start=1)
    )
    return f'''<div class="earthwork-visual">
      <svg viewBox="0 0 900 560" aria-label="放坡基坑土方几何计算动态图">
        <g class="earth-section-group">
          <path data-anim="earth-section" class="draw earth-surface" d="M45 118 H425" />
          <path data-anim="earth-cut" class="earth-cut" d="M88 118 L165 430 H305 L382 118 Z" />
          <path data-anim="earth-section" class="draw earth-outline" d="M88 118 L165 430 H305 L382 118" />
          <path data-anim="earth-dims" class="draw dimension" d="M70 118 V430 M58 118 H82 M58 430 H82" />
          <text data-anim="earth-dimlabels" class="dimension-label" x="34" y="282" text-anchor="middle" transform="rotate(-90 34 282)">深 {depth:g} m</text>
          <path data-anim="earth-dims" class="draw dimension" d="M165 466 H305 M165 454 V478 M305 454 V478" />
          <text data-anim="earth-dimlabels" class="dimension-label" x="235" y="510" text-anchor="middle">底宽 {bottom_width:g} m</text>
          <path data-anim="earth-dims" class="draw dimension" d="M88 82 H382 M88 70 V94 M382 70 V94" />
          <text data-anim="earth-dimlabels" class="dimension-label" x="235" y="55" text-anchor="middle">顶宽 {top_width:g} m</text>
          <text data-anim="earth-dimlabels" class="slope-label" x="342" y="270">放坡 {slope:g} : 1</text>
        </g>
        <g class="earth-plan" transform="translate(505 120)">
          <rect data-anim="earth-plans" class="plan-top" x="0" y="0" width="330" height="250" rx="8" />
          <rect data-anim="earth-plans" class="plan-mid" x="35" y="30" width="260" height="190" rx="6" />
          <rect data-anim="earth-plans" class="plan-bottom" x="70" y="60" width="190" height="130" rx="4" />
          <text data-anim="earth-plantexts" x="165" y="-26" text-anchor="middle">平面三截面</text>
          <text data-anim="earth-plantexts" x="165" y="78" text-anchor="middle">底 {bottom_length:g} × {bottom_width:g}</text>
          <text data-anim="earth-plantexts" x="165" y="120" text-anchor="middle">中 {mid_length:g} × {mid_width:g}</text>
          <text data-anim="earth-plantexts" x="165" y="162" text-anchor="middle">顶 {top_length:g} × {top_width:g}</text>
        </g>
      </svg>
      <div class="formula-stages">{step_html}</div>
    </div>'''


def cashflow_markup(segment: dict) -> str:
    data = dynamic_data(segment)
    flows = data.get("flows")
    if not flows or "rate" not in data:
        die(f"segment {segment.get('id', '?')} cashflow data must include flows and rate")
    rate = float(data["rate"])
    count = max(len(flows), 2)
    xs = [90 + index * (720 / (count - 1)) for index in range(count)]
    max_abs = max(max(abs(float(value)) for value in flows), 1.0)
    arrows = []
    labels = []
    discounted = []
    for index, raw_value in enumerate(flows):
        value = float(raw_value)
        x = xs[index]
        height = 70 + 125 * abs(value) / max_abs
        baseline = 270
        end_y = baseline - height if value >= 0 else baseline + height
        css = "positive" if value >= 0 else "negative"
        arrows.append(f'<line data-anim="cash-arrows" class="cash-arrow {css}" x1="{x:.1f}" y1="{baseline}" x2="{x:.1f}" y2="{end_y:.1f}" />')
        direction = -1 if value >= 0 else 1
        points = f"{x:.1f},{end_y:.1f} {x-10:.1f},{end_y+direction*18:.1f} {x+10:.1f},{end_y+direction*18:.1f}"
        arrows.append(f'<polygon data-anim="cash-marks" class="cash-head {css}" points="{points}" />')
        labels.append(f'<text data-anim="cash-marks" class="cash-label" x="{x:.1f}" y="{end_y + (-20 if value >= 0 else 34):.1f}" text-anchor="middle">{value:g}</text>')
        labels.append(f'<text data-anim="cash-periods" class="cash-period" x="{x + 24:.1f}" y="302" text-anchor="middle">{index}</text>')
        discounted.append(value / ((1 + rate) ** index))
    npv = sum(discounted)
    rows = "".join(
        f'<span data-anim="cash-discounts" class="discount-chip">第{index}期：{value:.2f}</span>'
        for index, value in enumerate(discounted[:6])
    )
    return f'''<div class="cashflow-visual">
      <svg viewBox="0 0 900 520" aria-label="现金流量与净现值动态图">
        <path data-anim="cash-axis" class="draw cash-axis" d="M55 270 H850" />
        {''.join(arrows)}
        {''.join(labels)}
        <text data-anim="cash-rate" class="cash-rate" x="450" y="470" text-anchor="middle">折现率 i = {rate * 100:g}%</text>
      </svg>
      <div class="discount-row">{rows}</div>
      <div data-anim="cash-result" class="cash-result">NPV = {npv:.2f}</div>
    </div>'''


def component_volume_markup(segment: dict) -> str:
    data = dynamic_data(segment)
    components = data.get("components")
    if not components:
        die(f"segment {segment.get('id', '?')} component_volume data must include components")
    blocks = []
    chips = []
    positions = [(130, 230, "column"), (390, 250, "beam"), (650, 170, "slab")]
    for index, item in enumerate(components[:3]):
        x, y, css = positions[index]
        label = e(item.get("label", f"构件{index + 1}"))
        formula = e(item.get("formula", ""))
        volume = float(item.get("volume", 0))
        if css == "column":
            shape = '<rect x="0" y="-150" width="86" height="220" rx="8"/><polygon points="0,-150 34,-178 120,-178 86,-150"/><polygon points="86,-150 120,-178 120,42 86,70"/>'
        elif css == "beam":
            shape = '<rect x="-80" y="-42" width="230" height="88" rx="7"/><polygon points="-80,-42 -38,-76 192,-76 150,-42"/><polygon points="150,-42 192,-76 192,12 150,46"/>'
        else:
            shape = '<rect x="-100" y="-52" width="230" height="106" rx="7"/><polygon points="-100,-52 -42,-94 188,-94 130,-52"/><polygon points="130,-52 188,-94 188,12 130,54"/>'
        blocks.append(f'<g data-anim="vol-blocks" class="volume-block {css}" transform="translate({x} {y})">{shape}<text x="45" y="118" text-anchor="middle">{label}</text></g>')
        chips.append(f'<div data-anim="vol-chips" class="volume-chip"><b>{label}</b><span>{formula}</span><strong>{volume:g} m³</strong></div>')
    total = sum(float(item.get("volume", 0)) for item in components[:3])
    return f'''<div class="component-volume-visual">
      <svg viewBox="0 0 900 520" aria-label="梁板柱构件体积拆分动态图">
        <path data-anim="vol-base" class="draw volume-base" d="M55 410 H845" />
        {''.join(blocks)}
      </svg>
      <div class="volume-chips">{''.join(chips)}</div>
      <div data-anim="vol-total" class="volume-total">合计 {total:g} m³</div>
    </div>'''


def flow_schedule_markup(segment: dict) -> str:
    data = dynamic_data(segment)
    if "sections" not in data or not data.get("processes"):
        die(f"segment {segment.get('id', '?')} flow_schedule data must include sections and processes")
    sections = int(data["sections"])
    processes = data["processes"]
    rhythm = float(data.get("rhythm", 2))
    total = (sections + len(processes) - 1) * rhythm
    left, top, plot_width = 120, 90, 690
    unit_width = plot_width / max(sections + len(processes) - 1, 1)
    row_height = 105
    grid = []
    blocks = []
    labels = []
    for tick in range(sections + len(processes)):
        x = left + tick * unit_width
        grid.append(f'<path data-anim="flow-grid" class="draw flow-grid" d="M{x:.1f} {top} V{top + row_height * len(processes)}" />')
        labels.append(f'<text data-anim="flow-times" class="flow-time" x="{x:.1f}" y="{top - 24}" text-anchor="middle">{tick * rhythm:g}</text>')
    for row, process in enumerate(processes):
        y = top + row * row_height
        labels.append(f'<text data-anim="flow-procs" class="flow-process" x="65" y="{y + 62}" text-anchor="middle">{e(process)}</text>')
        for section in range(sections):
            x = left + (row + section) * unit_width + 5
            blocks.append(f'<g data-anim="flow-blocks" class="flow-block process-{row}" transform="translate({x:.1f} {y + 15:.1f})"><rect width="{unit_width - 10:.1f}" height="72" rx="12"/><text x="{(unit_width - 10)/2:.1f}" y="46" text-anchor="middle">{section + 1}段</text></g>')
    grid.append(f'<path data-anim="flow-grid" class="draw flow-grid" d="M{left} {top + row_height * len(processes)} H{left + plot_width}" />')
    metrics = (
        f'<span data-anim="flow-metrics">施工段 m={sections}</span>'
        f'<span data-anim="flow-metrics">过程 n={len(processes)}</span>'
        f'<span data-anim="flow-metrics">节拍 K={rhythm:g}天</span>'
    )
    return f'''<div class="flow-schedule-visual">
      <svg viewBox="0 0 900 520" aria-label="等节奏流水施工进度动态图">
        {''.join(grid)}
        {''.join(blocks)}
        {''.join(labels)}
      </svg>
      <div class="flow-metrics">{metrics}</div>
      <div data-anim="flow-result" class="flow-result">T = (m+n-1)K = {total:g}天</div>
    </div>'''


def rebar_markup(segment: dict) -> str:
    """Rebar cutting length: sequential segment drawing, bend markers, length bars."""
    data = dynamic_data(segment)
    rebar_segments = data.get("segments")
    if not rebar_segments:
        die(f"segment {segment.get('id', '?')} rebar data must include segments")
    unit = str(data.get("unit", "mm"))

    # Trace the polyline in raw units, turning at each bend.
    heading = 0.0  # degrees, 0 = +x, positive turns counter-clockwise (SVG y down handled below)
    points: list[tuple[float, float]] = [(0.0, 0.0)]
    joints: list[dict] = []
    for index, item in enumerate(rebar_segments):
        turn = float(item.get("turn", 0))
        if turn:
            # A turn before the first segment only sets the initial orientation.
            if index > 0:
                joints.append({"point": points[-1], "angle": turn, "label": item.get("bend_label", f"{abs(turn):g}°")})
            heading += turn
        length = float(item.get("length", 0))
        radians = math.radians(heading)
        px, py = points[-1]
        points.append((px + length * math.cos(radians), py - length * math.sin(radians)))

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    span_x = max(xs) - min(xs) or 1.0
    span_y = max(ys) - min(ys) or 1.0
    pad = 70
    draw_w, draw_h = 900 - 2 * pad, 330 - pad
    scale = min(draw_w / span_x, draw_h / span_y)
    offset_x = pad + (draw_w - span_x * scale) / 2 - min(xs) * scale
    offset_y = 60 + (draw_h - span_y * scale) / 2 - min(ys) * scale

    def sx(p: tuple[float, float]) -> tuple[float, float]:
        return (p[0] * scale + offset_x, p[1] * scale + offset_y)

    paths = []
    dims = []
    for index, item in enumerate(rebar_segments):
        if float(item.get("length", 0)) <= 0:
            continue
        a, b = sx(points[index]), sx(points[index + 1])
        paths.append(f'<path data-anim="rebar-path" class="rebar-seg" d="M {a[0]:.1f} {a[1]:.1f} L {b[0]:.1f} {b[1]:.1f}" />')
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        # Perpendicular offset for the dimension label.
        dx, dy = b[0] - a[0], b[1] - a[1]
        norm = max(math.hypot(dx, dy), 1.0)
        ox, oy = -dy / norm * 30, dx / norm * 30
        dims.append(
            f'<text data-anim="rebar-dims" class="rebar-dim" x="{mx + ox:.1f}" y="{my + oy:.1f}" text-anchor="middle">'
            f'{e(item.get("label", ""))} {float(item.get("length", 0)):g}</text>'
        )
    bends = []
    for joint in joints:
        jx, jy = sx(joint["point"])
        bends.append(
            f'<g data-anim="rebar-bends" class="rebar-bend" transform="translate({jx:.1f} {jy:.1f})">'
            f'<circle r="19"/><text text-anchor="middle" y="5">{e(joint["label"])}</text></g>'
        )

    total = sum(float(item.get("length", 0)) for item in rebar_segments)
    declared_total = data.get("total")
    if declared_total is not None and abs(float(declared_total) - total) > 0.51:
        die(
            f"segment {segment.get('id', '?')} rebar total {declared_total} does not match "
            f"sum of segment lengths {total:g}"
        )
    bar_left, bar_width, bar_y = 90, 720, 420
    bars = []
    cursor = 0.0
    for index, item in enumerate(rebar_segments):
        length = float(item.get("length", 0))
        if length <= 0:
            continue
        width = length / total * bar_width if total else 0
        bars.append(
            f'<g data-anim="rebar-bars" class="rebar-bar part-{index % 3}" transform="translate({bar_left + cursor:.1f} {bar_y})">'
            f'<rect width="{width:.1f}" height="44" rx="8"/>'
            f'<text x="{width / 2:.1f}" y="29" text-anchor="middle">{length:g}</text></g>'
        )
        cursor += width
    return f'''<div class="rebar-visual">
      <svg viewBox="0 0 900 520" aria-label="钢筋下料长度分段累加动态图">
        {''.join(paths)}
        {''.join(bends)}
        {''.join(dims)}
        <text class="rebar-bar-title" x="90" y="400">分段累加（{e(unit)}）</text>
        {''.join(bars)}
      </svg>
      <div data-anim="rebar-result" class="rebar-result">几何分段和 = {total:g} {e(unit)}</div>
    </div>'''


def earned_value_markup(segment: dict) -> str:
    """Earned value: PV/EV/AC curves grow, variance gaps pop, metric chips land."""
    data = dynamic_data(segment)
    periods = data.get("periods")
    pv, ev, ac = data.get("pv"), data.get("ev"), data.get("ac")
    if not periods or not pv or not ev or not ac:
        die(f"segment {segment.get('id', '?')} earned_value data must include periods, pv, ev, ac")
    if not (len(periods) == len(pv) == len(ev) == len(ac)):
        die(f"segment {segment.get('id', '?')} earned_value series lengths differ")
    unit = str(data.get("unit", ""))
    left, right, top, bottom = 95, 855, 80, 400
    max_value = max(max(pv), max(ev), max(ac)) or 1.0
    count = len(periods)

    def px(index: int) -> float:
        return left + (right - left) * index / max(count - 1, 1)

    def py(value: float) -> float:
        return bottom - (bottom - top) * float(value) / max_value

    def polyline(series: list) -> str:
        return " ".join(f"{'M' if i == 0 else 'L'} {px(i):.1f} {py(v):.1f}" for i, v in enumerate(series))

    ticks = "".join(
        f'<text data-anim="ev-axes" class="ev-tick" x="{px(i):.1f}" y="{bottom + 34}" text-anchor="middle">{e(p)}</text>'
        for i, p in enumerate(periods)
    )
    focus = int(data.get("focus_period", count - 1))
    focus = min(max(focus, 0), count - 1)
    fx = px(focus)
    gaps = []
    sv = float(ev[focus]) - float(pv[focus])
    cv = float(ev[focus]) - float(ac[focus])
    gaps.append(
        f'<g data-anim="ev-gaps" class="ev-gap sv"><path d="M {fx - 8:.1f} {py(pv[focus]):.1f} H {fx + 8:.1f} M {fx:.1f} {py(pv[focus]):.1f} V {py(ev[focus]):.1f} M {fx - 8:.1f} {py(ev[focus]):.1f} H {fx + 8:.1f}"/>'
        f'<text x="{fx + 16:.1f}" y="{(py(pv[focus]) + py(ev[focus])) / 2 + 6:.1f}">SV {sv:+g}</text></g>'
    )
    gaps.append(
        f'<g data-anim="ev-gaps" class="ev-gap cv"><path d="M {fx - 44:.1f} {py(ac[focus]):.1f} H {fx - 28:.1f} M {fx - 36:.1f} {py(ac[focus]):.1f} V {py(ev[focus]):.1f} M {fx - 44:.1f} {py(ev[focus]):.1f} H {fx - 28:.1f}"/>'
        f'<text x="{fx - 52:.1f}" y="{(py(ac[focus]) + py(ev[focus])) / 2 + 6:.1f}" text-anchor="end">CV {cv:+g}</text></g>'
    )
    metrics = data.get("metrics") or []
    chips = "".join(f'<span data-anim="ev-chips" class="ev-chip">{e(item)}</span>' for item in metrics[:4])
    unit_label = f'<text data-anim="ev-axes" class="ev-tick" x="{left - 12}" y="{top - 16}" text-anchor="start">{e(unit)}</text>' if unit else ""
    return f'''<div class="earned-value-visual">
      <svg viewBox="0 0 900 520" aria-label="挣值法三曲线与偏差动态图">
        <path data-anim="ev-axes" class="draw ev-axis" d="M {left} {top - 20} V {bottom} H {right + 10}" />
        {ticks}
        {unit_label}
        <g data-anim="ev-legend" class="ev-legend" transform="translate({right - 240} {top - 24})">
          <rect class="lg pv" x="0" y="-10" width="26" height="8" rx="4"/><text x="34" y="0">PV 计划</text>
          <rect class="lg ev" x="100" y="-10" width="26" height="8" rx="4"/><text x="134" y="0">EV 挣值</text>
          <rect class="lg ac" x="200" y="-10" width="26" height="8" rx="4"/><text x="234" y="0">AC 实际</text>
        </g>
        <path data-anim="ev-pv" class="ev-line pv" d="{polyline(pv)}" />
        <path data-anim="ev-ev" class="ev-line ev" d="{polyline(ev)}" />
        <path data-anim="ev-ac" class="ev-line ac" d="{polyline(ac)}" />
        {''.join(gaps)}
      </svg>
      <div class="ev-chips">{chips}</div>
    </div>'''


def projection_markup(segment: dict) -> str:
    """Three-plane projection system (H/V/W): axonometric build-up or unfolded layout."""
    data = dynamic_data(segment)
    stage = str(data.get("stage", "system"))
    if stage not in {"system", "unfold"}:
        die(f"segment {segment.get('id', '?')} projection stage must be 'system' or 'unfold'")
    point = data.get("point")
    if not isinstance(point, dict):
        die(f"segment {segment.get('id', '?')} projection data must include point {{x,y,z}}")
    pax, pay, paz = (float(point.get(axis, -1)) for axis in ("x", "y", "z"))
    extent = data.get("extent") or {}
    ext_x = float(extent.get("x", 40))
    ext_y = float(extent.get("y", 24))
    ext_z = float(extent.get("z", 30))
    if not (0 < pax < ext_x and 0 < pay < ext_y and 0 < paz < ext_z):
        die(
            f"segment {segment.get('id', '?')} projection point ({pax:g},{pay:g},{paz:g}) "
            f"must lie strictly inside extent ({ext_x:g},{ext_y:g},{ext_z:g})"
        )
    label = e(data.get("point_label", "A"))
    result_label = data.get("result_label", "")

    if stage == "system":
        scale = 9.0
        rec_x, rec_y = 0.58 * scale, 0.40 * scale  # oblique Y-axis recession per unit
        origin_x, origin_y = 585.0, 335.0

        def m3(x: float, y: float, z: float) -> tuple[float, float]:
            return (origin_x - x * scale + y * rec_x, origin_y - z * scale + y * rec_y)

        def pts(*coords: tuple[float, float, float]) -> str:
            return " ".join(f"{px:.1f},{py:.1f}" for px, py in (m3(*c) for c in coords))

        plane_v = pts((0, 0, 0), (ext_x, 0, 0), (ext_x, 0, ext_z), (0, 0, ext_z))
        plane_h = pts((0, 0, 0), (ext_x, 0, 0), (ext_x, ext_y, 0), (0, ext_y, 0))
        plane_w = pts((0, 0, 0), (0, ext_y, 0), (0, ext_y, ext_z), (0, 0, ext_z))
        axis_x, axis_y, axis_z = m3(ext_x + 7, 0, 0), m3(0, ext_y + 6, 0), m3(0, 0, ext_z + 6)
        spot = m3(pax, pay, paz)
        foot_h, foot_v, foot_w = m3(pax, pay, 0), m3(pax, 0, paz), m3(0, pay, paz)
        letter_v, letter_h, letter_w = m3(ext_x - 5, 0, ext_z - 6), m3(ext_x - 6, ext_y - 5, 0), m3(0, ext_y - 2, ext_z - 3.5)

        # A scene that only introduces the plane system can hide rays/feet via
        # projection.show_projections = false (they are omitted, not just static).
        if data.get("show_projections", True):
            feet = "".join(
                f'<g data-anim="proj-feet" class="proj-foot">'
                f'<circle cx="{fx:.1f}" cy="{fy:.1f}" r="7"/>'
                f'<text x="{fx + dx:.1f}" y="{fy + dy:.1f}">{text}</text></g>'
                for (fx, fy), (dx, dy), text in (
                    (foot_h, (14, 26), f"{label.lower()}"),
                    (foot_v, (-34, -14), f"{label.lower()}′"),
                    (foot_w, (14, 28), f"{label.lower()}″"),
                )
            )
            rays = "".join(
                f'<line data-anim="proj-rays" class="proj-ray" x1="{spot[0]:.1f}" y1="{spot[1]:.1f}" x2="{fx:.1f}" y2="{fy:.1f}"/>'
                for fx, fy in (foot_h, foot_v, foot_w)
            )
        else:
            feet = ""
            rays = ""
        default_result = "两面定位置，三面定形体"
        body = f'''
        <polygon data-anim="proj-planes" class="proj-plane" points="{plane_v}"/>
        <polygon data-anim="proj-planes" class="proj-plane" points="{plane_h}"/>
        <polygon data-anim="proj-planes" class="proj-plane" points="{plane_w}"/>
        <line data-anim="proj-planes" class="proj-axis" x1="{origin_x}" y1="{origin_y}" x2="{axis_x[0]:.1f}" y2="{axis_x[1]:.1f}"/>
        <line data-anim="proj-planes" class="proj-axis" x1="{origin_x}" y1="{origin_y}" x2="{axis_y[0]:.1f}" y2="{axis_y[1]:.1f}"/>
        <line data-anim="proj-planes" class="proj-axis" x1="{origin_x}" y1="{origin_y}" x2="{axis_z[0]:.1f}" y2="{axis_z[1]:.1f}"/>
        <text data-anim="proj-labels" class="proj-plane-letter" x="{letter_v[0]:.1f}" y="{letter_v[1]:.1f}">V</text>
        <text data-anim="proj-labels" class="proj-plane-letter" x="{letter_h[0]:.1f}" y="{letter_h[1]:.1f}">H</text>
        <text data-anim="proj-labels" class="proj-plane-letter" x="{letter_w[0]:.1f}" y="{letter_w[1]:.1f}">W</text>
        <text data-anim="proj-labels" class="proj-axis-label" x="{axis_x[0] - 26:.1f}" y="{axis_x[1] - 8:.1f}">X</text>
        <text data-anim="proj-labels" class="proj-axis-label" x="{axis_y[0] + 8:.1f}" y="{axis_y[1] + 20:.1f}">Y</text>
        <text data-anim="proj-labels" class="proj-axis-label" x="{axis_z[0] + 10:.1f}" y="{axis_z[1] + 4:.1f}">Z</text>
        <text data-anim="proj-labels" class="proj-axis-label" x="{origin_x + 10:.1f}" y="{origin_y + 24:.1f}">O</text>
        <g data-anim="proj-point" class="proj-point"><circle cx="{spot[0]:.1f}" cy="{spot[1]:.1f}" r="9"/>
          <text x="{spot[0] + 14:.1f}" y="{spot[1] - 12:.1f}">{label}</text></g>
        {rays}
        {feet}'''
    else:
        origin_x, origin_y = 470.0, 258.0
        s2 = 8.0
        len_x, len_y, len_z = ext_x * s2 + 34, ext_y * s2 + 34, ext_z * s2 + 30
        foot_v = (origin_x - pax * s2, origin_y - paz * s2)
        foot_w = (origin_x + pay * s2, origin_y - paz * s2)
        foot_h = (origin_x - pax * s2, origin_y + pay * s2)
        feet = "".join(
            f'<g data-anim="proj-feet" class="proj-foot">'
            f'<circle cx="{fx:.1f}" cy="{fy:.1f}" r="7"/>'
            f'<text x="{fx + dx:.1f}" y="{fy + dy:.1f}">{text}</text></g>'
            for (fx, fy), (dx, dy), text in (
                (foot_v, (-36, -12), f"{label.lower()}′"),
                (foot_w, (14, -12), f"{label.lower()}″"),
                (foot_h, (14, 24), f"{label.lower()}"),
            )
        )
        default_result = "V 不动｜H 下转 90°｜W 后转 90°"
        body = f'''
        <rect data-anim="proj-planes" class="proj-plane" x="{origin_x - len_x:.1f}" y="{origin_y - len_z:.1f}" width="{len_x:.1f}" height="{len_z:.1f}"/>
        <rect data-anim="proj-planes" class="proj-plane" x="{origin_x:.1f}" y="{origin_y - len_z:.1f}" width="{len_y:.1f}" height="{len_z:.1f}"/>
        <rect data-anim="proj-planes" class="proj-plane" x="{origin_x - len_x:.1f}" y="{origin_y:.1f}" width="{len_x:.1f}" height="{len_y:.1f}"/>
        <text data-anim="proj-labels" class="proj-plane-letter" x="{origin_x - len_x + 18:.1f}" y="{origin_y - len_z + 40:.1f}">V</text>
        <text data-anim="proj-labels" class="proj-plane-letter" x="{origin_x + len_y - 42:.1f}" y="{origin_y - len_z + 40:.1f}">W</text>
        <text data-anim="proj-labels" class="proj-plane-letter" x="{origin_x - len_x + 18:.1f}" y="{origin_y + len_y - 18:.1f}">H</text>
        <text data-anim="proj-labels" class="proj-axis-label" x="{origin_x - len_x - 28:.1f}" y="{origin_y - 10:.1f}">X</text>
        <text data-anim="proj-labels" class="proj-axis-label" x="{origin_x + 12:.1f}" y="{origin_y - len_z - 12:.1f}">Z</text>
        <text data-anim="proj-labels" class="proj-axis-label" x="{origin_x + 12:.1f}" y="{origin_y + 26:.1f}">O</text>
        <path data-anim="proj-arrows" class="proj-arrow" d="M {origin_x - len_x * 0.62:.1f} {origin_y - 58:.1f} q -46 58 0 112"/>
        <polygon data-anim="proj-arrows" class="proj-arrow-head" points="{origin_x - len_x * 0.62:.1f},{origin_y + 54:.1f} {origin_x - len_x * 0.62 - 16:.1f},{origin_y + 40:.1f} {origin_x - len_x * 0.62 + 6:.1f},{origin_y + 36:.1f}"/>
        <text data-anim="proj-arrows" class="proj-arrow-label" x="{origin_x - len_x * 0.62 - 124:.1f}" y="{origin_y - 70:.1f}">沿OX下转90°</text>
        <path data-anim="proj-arrows" class="proj-arrow" d="M {origin_x + 58:.1f} {origin_y - len_z * 0.62:.1f} q 58 -46 112 0"/>
        <polygon data-anim="proj-arrows" class="proj-arrow-head" points="{origin_x + 170:.1f},{origin_y - len_z * 0.62:.1f} {origin_x + 156:.1f},{origin_y - len_z * 0.62 - 16:.1f} {origin_x + 152:.1f},{origin_y - len_z * 0.62 + 6:.1f}"/>
        <text data-anim="proj-arrows" class="proj-arrow-label" x="{origin_x + 62:.1f}" y="{origin_y - len_z * 0.62 - 26:.1f}">沿OZ后转90°</text>
        <text data-anim="proj-arrows" class="proj-axis-label" x="{origin_x - 52:.1f}" y="{origin_y + len_y + 26:.1f}">Y<tspan dy="6" font-size="72%">H</tspan></text>
        <text data-anim="proj-arrows" class="proj-axis-label" x="{origin_x + len_y + 8:.1f}" y="{origin_y - 10:.1f}">Y<tspan dy="6" font-size="72%">W</tspan></text>
        <line data-anim="proj-rays" class="proj-ray" x1="{foot_v[0]:.1f}" y1="{foot_v[1]:.1f}" x2="{foot_h[0]:.1f}" y2="{foot_h[1]:.1f}"/>
        <line data-anim="proj-rays" class="proj-ray" x1="{foot_v[0]:.1f}" y1="{foot_v[1]:.1f}" x2="{foot_w[0]:.1f}" y2="{foot_w[1]:.1f}"/>
        {feet}'''

    result_html = (
        f'<div data-anim="proj-result" class="proj-result">{e(result_label or default_result)}</div>'
    )
    return f'''<div class="projection-visual">
      <svg viewBox="0 0 900 520" aria-label="三面投影体系动态图">{body}
      </svg>
      {result_html}
    </div>'''


# ---------------------------------------------------------------------------
# Generic visual markup
# ---------------------------------------------------------------------------


def visual_markup(segment: dict) -> str:
    visual_type = segment.get("visual_type", "concept")
    bullets = [e(item) for item in segment.get("bullets", []) if str(item).strip()]
    steps = [e(item) for item in segment.get("steps", []) if str(item).strip()]
    key_number = e(segment.get("key_number", ""))
    formula = e(segment.get("formula", ""))

    builders = {
        "network-plan": network_plan_markup,
        "earthwork-volume": earthwork_markup,
        "cashflow": cashflow_markup,
        "component-volume": component_volume_markup,
        "flow-schedule": flow_schedule_markup,
        "rebar-length": rebar_markup,
        "earned-value": earned_value_markup,
        "projection-point": projection_markup,
    }
    if visual_type in builders:
        return builders[visual_type](segment)

    if visual_type in {"process", "timeline"}:
        items = steps or bullets or ["前置条件", "关键工序", "检查验收"]
        cards = []
        for index, item in enumerate(items[:5], start=1):
            cards.append(f'<div data-anim="step-items" class="step"><span>{index:02d}</span><strong>{item}</strong></div>')
        connector = '<i data-anim="step-items" class="flow-line"></i>'
        return '<div class="step-flow">' + connector.join(cards) + "</div>"

    if visual_type == "comparison":
        comparison = segment.get("comparison") or {}
        left_title = e(comparison.get("left_title", "正确做法"))
        right_title = e(comparison.get("right_title", "常见错误"))
        left = comparison.get("left") or bullets[:2] or ["按设计与现行口径执行"]
        right = comparison.get("right") or bullets[2:4] or ["省略条件或混淆顺序"]
        left_items = "".join(f'<li data-anim="cmp-points">{e(item)}</li>' for item in left)
        right_items = "".join(f'<li data-anim="cmp-points">{e(item)}</li>' for item in right)
        return (
            '<div class="comparison">'
            f'<section data-anim="cmp-left" class="good"><b>{left_title}</b><ul>{left_items}</ul></section>'
            f'<section data-anim="cmp-right" class="bad"><b>{right_title}</b><ul>{right_items}</ul></section>'
            "</div>"
        )

    if visual_type == "calculation":
        items = steps or bullets or ["列出条件", "统一单位", "代入复算"]
        return (
            '<div class="calculation">'
            f'<div data-anim="calc-formula" class="formula">{formula or "公式与单位"}</div>'
            + "".join(f'<div data-anim="calc-steps" class="calc-step"><span>{i}</span>{item}</div>' for i, item in enumerate(items[:4], start=1))
            + (f'<div data-anim="calc-result" class="key-number">{key_number}</div>' if key_number else "")
            + "</div>"
        )

    if visual_type == "summary":
        pills = bullets or steps or ["条件", "顺序", "检查", "来源"]
        pill_html = "".join(f'<span data-anim="sum-pills">{item}</span>' for item in pills[:5])
        return (
            '<div class="summary-visual">'
            f'<div data-anim="sum-number" class="key-number">{key_number or "记条件 · 记顺序"}</div>'
            f'<div class="pill-row">{pill_html}</div>'
            "</div>"
        )

    return f'''<div class="concept-visual">
      <svg viewBox="0 0 760 520" aria-hidden="true">
        <path data-anim="concept-lines" class="draw" d="M120 420V175L375 65l265 110v245" />
        <path data-anim="concept-lines" class="draw secondary" d="M170 420V210h410v210M260 420V265h95v155M430 420V265h95v155" />
        <path data-anim="concept-lines" class="draw accent" d="M85 420h590M210 154l165-72 170 72" />
        <circle data-anim="concept-pulse" class="pulse" cx="375" cy="235" r="44" />
        <path data-anim="concept-arrow" class="accent-arrow" d="M375 188v94m-18-20 18 20 18-20" />
      </svg>
      {f'<div data-anim="concept-number" class="key-number">{key_number}</div>' if key_number else ''}
    </div>'''


def scene_markup(segment: dict, index: int, total: int, timeline_rows: list[dict], project_label: str) -> str:
    bullets = [item for item in segment.get("bullets", []) if str(item).strip()]
    bullet_html = "".join(f'<li data-anim="card-bullets">{e(item)}</li>' for item in bullets[:4])
    source_label = e(segment.get("source_label", "来源见证据包"))
    anim = segment.get("animation") or {}
    mode = anim.get("mode", "build")
    rail_cells = []
    for j, row in enumerate(timeline_rows, start=1):
        status = "done" if j < index else ("current" if j == index else "todo")
        fill = '<i class="rail-fill"></i>' if j == index else ""
        rail_cells.append(f'<span class="rail-seg {status}" style="flex-grow:{row["duration"]:.3f}">{fill}</span>')
    return f'''<section class="scene" id="s{index}" data-mode="{mode}">
      <div class="paper-grid" data-layout-ignore></div>
      <div class="ghost-num" aria-hidden="true" data-layout-ignore>{index:02d}</div>
      <div class="corner-ring" aria-hidden="true" data-layout-ignore></div>
      <header class="topline">
        <div class="brand-lockup">
          <span class="brand-mark" aria-hidden="true"></span>
          <span class="brand" data-layout-allow-overflow data-layout-allow-overlap>建知课</span>
          <span class="brand-sub" data-layout-allow-overlap>{e(project_label)}</span>
        </div>
        <div class="scene-meta">
          <span class="scene-count" data-layout-allow-overlap>{index:02d} / {total:02d}</span>
          <span class="section-tag" data-layout-allow-overlap>{e(segment.get('title', f'场景 {index}'))}</span>
        </div>
      </header>
      <div class="progress-rail" aria-hidden="true" data-layout-ignore>{''.join(rail_cells)}</div>
      <main class="main-grid">
        <div class="visual-panel">
          <i class="corner c-tl"></i><i class="corner c-tr"></i><i class="corner c-bl"></i><i class="corner c-br"></i>
          {visual_markup(segment)}
        </div>
        <article class="knowledge-card">
          <p class="eyebrow"><span class="eyebrow-index">{index:02d}</span>{e(segment.get('title', '核心知识'))}</p>
          <h1>{e(segment.get('headline', segment.get('title', '核心知识')))}</h1>
          <span class="headline-line" aria-hidden="true"></span>
          <ul>{bullet_html}</ul>
        </article>
      </main>
      <footer class="source-label"><span class="stamp" data-layout-allow-overlap>依据</span><span class="source-text" data-layout-allow-overlap>{source_label}</span></footer>
    </section>'''


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------


def build_css(profile: str) -> str:
    width, height = PROFILES[profile]
    v = profile == "vertical"

    def pick(vertical_value: str, landscape_value: str) -> str:
        return vertical_value if v else landscape_value

    margin = pick("56px", "84px")
    return f"""
    @font-face {{ font-family: "PingFang SC"; src: local("PingFang SC"); }}
    @font-face {{ font-family: "Songti SC"; src: local("Songti SC"); }}
    @font-face {{ font-family: "Noto Sans CJK SC"; src: local("Noto Sans CJK SC"); }}
    :root {{
      --bg:#F3F0E8; --ink:#24313F; --accent:#B9541B; --accent-bright:#E97932;
      --steel:#526577; --paper:#FCFAF5; --danger:#A9342D;
      --line-soft:rgba(82,101,119,.22); --line-faint:rgba(102,119,137,.10);
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ width:{width}px; height:{height}px; overflow:hidden; background:var(--bg); color:var(--ink); font-family:"PingFang SC","Noto Sans CJK SC",sans-serif; }}
    #root {{ position:relative; width:{width}px; height:{height}px; overflow:hidden; }}
    .scene {{ position:absolute; inset:0; overflow:hidden; background:var(--bg); }}
    .scene + .scene {{ opacity:0; display:none; }}

    /* Background layers */
    .paper-grid {{ position:absolute; inset:-80px; opacity:.5; background-image:linear-gradient(var(--line-faint) 1px,transparent 1px),linear-gradient(90deg,var(--line-faint) 1px,transparent 1px); background-size:{pick('54px 54px','64px 64px')}; }}
    .ghost-num {{ position:absolute; z-index:0; {pick('top:120px; right:-20px;','bottom:-90px; left:26px;')} font:800 {pick('440px','400px')}/1 "Songti SC",serif; color:rgba(36,49,63,.045); letter-spacing:-.04em; }}
    .corner-ring {{ position:absolute; z-index:0; right:{pick('-90px','-60px')}; bottom:{pick('150px','-120px')}; width:{pick('400px','380px')}; height:{pick('400px','380px')}; border:2px dashed rgba(82,101,119,.16); border-radius:50%; outline:38px double rgba(82,101,119,.07); outline-offset:-58px; }}

    /* Topline + progress */
    .topline {{ position:absolute; z-index:4; left:{margin}; right:{margin}; top:{pick('64px','46px')}; display:flex; justify-content:space-between; align-items:baseline; }}
    .brand-lockup {{ display:flex; align-items:baseline; gap:16px; flex:1 1 auto; min-width:0; margin-right:28px; }}
    .brand-mark {{ align-self:center; flex-shrink:0; width:{pick('18px','16px')}; height:{pick('18px','16px')}; background:var(--accent); transform:rotate(45deg); border-radius:3px; }}
    .brand {{ color:var(--accent); font-weight:800; letter-spacing:.2em; font-size:{pick('30px','26px')}; white-space:nowrap; flex-shrink:0; }}
    .brand-sub {{ color:var(--steel); font-size:{pick('20px','18px')}; letter-spacing:.04em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; }}
    .scene-meta {{ display:flex; align-items:baseline; gap:18px; flex-shrink:0; }}
    .scene-count {{ color:var(--steel); font-size:{pick('21px','19px')}; font-variant-numeric:tabular-nums; letter-spacing:.12em; white-space:nowrap; }}
    .section-tag {{ color:var(--ink); font-weight:700; font-size:{pick('29px','25px')}; border-bottom:3px solid var(--accent-bright); padding-bottom:8px; white-space:nowrap; }}
    .progress-rail {{ position:absolute; z-index:4; left:{margin}; right:{margin}; top:{pick('128px','104px')}; height:6px; display:flex; gap:6px; }}
    .rail-seg {{ position:relative; height:100%; border-radius:3px; background:rgba(82,101,119,.16); overflow:hidden; }}
    .rail-seg.done {{ background:var(--accent-bright); opacity:.85; }}
    .rail-fill {{ position:absolute; inset:0; background:var(--accent); border-radius:3px; transform:scaleX(0); transform-origin:left center; }}

    /* Main grid */
    .main-grid {{ position:absolute; z-index:2; left:{margin}; right:{margin}; top:{pick('178px','148px')}; bottom:{pick('252px','168px')}; display:grid; grid-template-columns:{pick('1fr','1.22fr .9fr')}; grid-template-rows:{pick('1.12fr .88fr','1fr')}; gap:{pick('40px','56px')}; align-items:stretch; }}
    .visual-panel {{ position:relative; min-height:0; display:flex; align-items:center; justify-content:center; border:2px solid rgba(102,119,137,.20); border-radius:30px; background:rgba(252,250,245,.6); box-shadow:0 18px 50px rgba(36,49,63,.07); padding:{pick('30px','38px')}; overflow:hidden; }}
    .visual-panel::before {{ content:""; position:absolute; inset:0; background-image:linear-gradient(rgba(102,119,137,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(102,119,137,.05) 1px,transparent 1px); background-size:27px 27px; pointer-events:none; }}
    .corner {{ position:absolute; width:26px; height:26px; border:0 solid var(--accent-bright); opacity:.85; }}
    .c-tl {{ left:14px; top:14px; border-left-width:4px; border-top-width:4px; border-top-left-radius:8px; }}
    .c-tr {{ right:14px; top:14px; border-right-width:4px; border-top-width:4px; border-top-right-radius:8px; }}
    .c-bl {{ left:14px; bottom:14px; border-left-width:4px; border-bottom-width:4px; border-bottom-left-radius:8px; }}
    .c-br {{ right:14px; bottom:14px; border-right-width:4px; border-bottom-width:4px; border-bottom-right-radius:8px; }}

    /* Knowledge card */
    .knowledge-card {{ align-self:center; position:relative; background:rgba(252,250,245,.96); border-radius:26px; padding:{pick('40px 44px','46px 50px')}; box-shadow:0 24px 70px rgba(36,49,63,.12); border:1px solid rgba(102,119,137,.14); }}
    .knowledge-card::before {{ content:""; position:absolute; left:0; top:26px; bottom:26px; width:10px; border-radius:0 8px 8px 0; background:linear-gradient(180deg,var(--accent-bright),var(--accent)); }}
    .eyebrow {{ display:flex; align-items:center; gap:14px; color:var(--accent); font-weight:800; letter-spacing:.16em; font-size:{pick('24px','21px')}; margin-bottom:18px; }}
    .eyebrow-index {{ display:grid; place-items:center; min-width:{pick('44px','40px')}; height:{pick('44px','40px')}; border:2px solid var(--accent-bright); border-radius:12px; color:var(--accent); font-variant-numeric:tabular-nums; letter-spacing:0; font-size:{pick('22px','20px')}; }}
    h1 {{ font-family:"Songti SC",serif; font-size:{pick('60px','56px')}; line-height:1.18; margin-bottom:14px; }}
    .headline-line {{ display:block; width:96px; height:7px; margin-bottom:24px; border-radius:4px; background:var(--accent-bright); transform-origin:left center; }}
    .knowledge-card ul {{ list-style:none; display:grid; gap:17px; }}
    .knowledge-card li {{ font-size:{pick('30px','28px')}; line-height:1.45; padding-left:34px; position:relative; }}
    .knowledge-card li::before {{ content:""; position:absolute; left:0; top:.5em; width:13px; height:13px; border-radius:4px; background:var(--accent-bright); transform:rotate(45deg); }}

    /* Source + subtitles */
    .source-label {{ position:absolute; z-index:4; left:{margin}; bottom:{pick('198px','118px')}; display:flex; align-items:center; gap:12px; font-size:{pick('21px','18px')}; color:var(--steel); max-width:72%; }}
    .stamp {{ flex:none; padding:5px 12px; border:2px solid rgba(169,74,24,.55); border-radius:8px; color:#A34817; font-weight:800; letter-spacing:.2em; font-size:{pick('18px','16px')}; }}
    #subtitle-layer {{ position:absolute; z-index:20; left:{pick('50px','240px')}; right:{pick('50px','240px')}; bottom:{pick('66px','30px')}; height:{pick('116px','76px')}; display:flex; align-items:center; justify-content:center; }}
    .subtitle {{ position:absolute; opacity:0; max-width:100%; color:white; background:rgba(36,49,63,.93); border-radius:16px; padding:{pick('18px 30px 18px 38px','13px 28px 13px 34px')}; font-size:{pick('35px','30px')}; line-height:1.42; text-align:center; box-shadow:0 10px 34px rgba(36,49,63,.25); }}
    .subtitle::before {{ content:""; position:absolute; left:{pick('16px','14px')}; top:14px; bottom:14px; width:6px; border-radius:3px; background:var(--accent-bright); }}

    /* Shared visual pieces */
    .concept-visual,.summary-visual,.calculation {{ width:100%; height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:24px; }}
    .concept-visual svg {{ width:100%; height:78%; overflow:visible; }}
    .draw {{ fill:none; stroke:var(--ink); stroke-width:8; stroke-linecap:round; stroke-linejoin:round; }}
    .draw.secondary {{ stroke:var(--steel); stroke-width:6; }} .draw.accent,.accent-arrow {{ fill:none; stroke:var(--accent); stroke-width:10; stroke-linecap:round; stroke-linejoin:round; }}
    .pulse {{ fill:rgba(233,121,50,.10); stroke:var(--accent); stroke-width:7; }}
    .key-number {{ font:800 {pick('68px','62px')}/1.1 "Songti SC",serif; color:var(--accent); text-align:center; }}
    .step-flow {{ width:100%; display:flex; flex-direction:{pick('column','row')}; align-items:stretch; justify-content:center; gap:18px; }}
    .step {{ flex:1; min-height:{pick('104px','156px')}; display:flex; align-items:center; gap:22px; padding:24px; border-radius:20px; background:var(--paper); border:2px solid var(--line-soft); font-size:{pick('27px','24px')}; }}
    .step span,.calc-step span {{ flex:none; width:48px; height:48px; border-radius:14px; display:grid; place-items:center; background:var(--accent); color:white; font-weight:800; }}
    .flow-line {{ flex:none; width:{pick('4px','36px')}; height:{pick('26px','4px')}; align-self:center; border-radius:2px; background:var(--accent-bright); }}
    .comparison {{ width:100%; display:grid; grid-template-columns:1fr 1fr; gap:24px; }}
    .comparison section {{ min-height:320px; border-radius:24px; padding:32px; background:var(--paper); border:2px solid var(--line-soft); border-top:9px solid var(--accent); }}
    .comparison .bad {{ border-top-color:var(--danger); }} .comparison b {{ font-size:30px; }} .comparison ul {{ margin-top:24px; padding-left:28px; font-size:25px; line-height:1.55; }}
    .formula {{ padding:24px 36px; border:3px solid var(--accent); border-radius:18px; background:rgba(252,250,245,.85); font:700 {pick('48px','44px')}/1.2 "Songti SC",serif; color:var(--accent); }}
    .calc-step {{ width:90%; display:flex; gap:20px; align-items:center; padding:17px 24px; background:var(--paper); border:2px solid var(--line-soft); border-radius:16px; font-size:26px; }}
    .pill-row {{ display:flex; flex-wrap:wrap; gap:16px; justify-content:center; }} .pill-row span {{ padding:15px 24px; border-radius:999px; background:var(--paper); border:2px solid var(--steel); font-size:25px; }}

    /* Network plan */
    .network-visual,.earthwork-visual {{ width:100%; height:100%; min-height:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:18px; }}
    .network-visual svg {{ width:100%; height:78%; overflow:visible; }}
    .network-activity {{ fill:none; stroke:var(--steel); stroke-width:7; stroke-linecap:round; }}
    .network-arrow {{ fill:var(--steel); stroke:none; }}
    .network-node circle {{ fill:var(--paper); stroke:var(--ink); stroke-width:6; }}
    .network-node text {{ fill:var(--ink); font-size:30px; font-weight:800; }}
    .network-node .node-time {{ font-size:19px; font-weight:700; }}
    .network-node .node-time-early {{ fill:var(--accent); }}
    .network-node .node-time-late {{ fill:var(--steel); }}
    .network-label rect {{ fill:var(--paper); stroke:rgba(82,101,119,.32); stroke-width:2; }}
    .network-label text {{ fill:var(--ink); font-size:18px; font-weight:700; }}
    .metric-row {{ display:flex; flex-wrap:wrap; gap:14px; justify-content:center; }}
    .metric-chip {{ padding:11px 18px; border-radius:999px; background:var(--paper); border:2px solid var(--steel); color:var(--ink); font-size:{pick('21px','19px')}; font-weight:700; }}

    /* Earthwork */
    .earthwork-visual svg {{ width:100%; height:66%; overflow:visible; }}
    .earth-cut {{ fill:rgba(233,121,50,.18); transform-box:fill-box; transform-origin:center top; }}
    .earth-outline,.earth-surface {{ fill:none; stroke:var(--ink); stroke-width:6; stroke-linecap:round; stroke-linejoin:round; }}
    .dimension {{ fill:none; stroke:var(--accent); stroke-width:4; stroke-linecap:round; }}
    .dimension-label,.slope-label,.earth-plan text {{ fill:var(--ink); font-size:22px; font-weight:700; }}
    .slope-label {{ fill:var(--accent); }}
    .earth-plan rect {{ fill:rgba(252,250,245,.9); stroke:var(--steel); stroke-width:4; transform-box:fill-box; transform-origin:center; }}
    .earth-plan .plan-mid {{ fill:rgba(82,101,119,.10); }} .earth-plan .plan-bottom {{ fill:rgba(233,121,50,.20); stroke:var(--accent); }}
    .formula-stages {{ width:100%; display:grid; grid-template-columns:{pick('1fr 1fr','repeat(4,1fr)')}; gap:12px; }}
    .formula-stage {{ min-height:68px; display:flex; align-items:center; gap:12px; padding:12px 14px; border-radius:15px; background:var(--paper); border:2px solid var(--line-soft); font-size:{pick('20px','17px')}; line-height:1.35; }}
    .formula-stage span {{ flex:none; width:34px; height:34px; border-radius:10px; display:grid; place-items:center; background:var(--accent); color:white; font-weight:800; }}

    /* Cashflow / component volume / flow schedule */
    .cashflow-visual,.component-volume-visual,.flow-schedule-visual,.rebar-visual,.earned-value-visual,.projection-visual {{ width:100%; height:100%; min-height:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:14px; }}
    .cashflow-visual svg,.component-volume-visual svg,.flow-schedule-visual svg,.rebar-visual svg,.earned-value-visual svg,.projection-visual svg {{ width:100%; height:{pick('65%','68%')}; overflow:visible; }}
    .cash-axis {{ stroke:var(--ink); stroke-width:6; }}
    .cash-arrow {{ stroke-width:10; stroke-linecap:round; transform-box:fill-box; transform-origin:center bottom; }}
    .cash-arrow.positive {{ stroke:var(--accent); }} .cash-arrow.negative {{ stroke:var(--danger); }}
    .cash-head.positive {{ fill:var(--accent); }} .cash-head.negative {{ fill:var(--danger); }}
    .cash-label {{ fill:var(--ink); font-size:24px; font-weight:800; }} .cash-period,.cash-rate {{ fill:var(--steel); font-size:21px; font-weight:700; }}
    .discount-row {{ width:100%; display:flex; flex-wrap:wrap; gap:10px; justify-content:center; }}
    .discount-chip {{ padding:10px 14px; border:2px solid rgba(82,101,119,.28); border-radius:999px; background:var(--paper); font-size:{pick('18px','16px')}; }}
    .cash-result,.volume-total,.flow-result,.rebar-result {{ color:var(--accent); font:800 {pick('44px','38px')}/1.1 "Songti SC",serif; }}
    .volume-block {{ transform-box:fill-box; transform-origin:center; }}
    .volume-block rect,.volume-block polygon {{ stroke:var(--ink); stroke-width:4; }}
    .volume-block.column rect,.volume-block.column polygon {{ fill:rgba(233,121,50,.23); }}
    .volume-block.beam rect,.volume-block.beam polygon {{ fill:rgba(82,101,119,.17); }}
    .volume-block.slab rect,.volume-block.slab polygon {{ fill:rgba(185,84,27,.14); }}
    .volume-block text {{ fill:var(--ink); font-size:27px; font-weight:800; }}
    .volume-chips {{ width:100%; display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
    .volume-chip {{ display:grid; grid-template-columns:auto 1fr; gap:5px 10px; padding:12px; border-radius:14px; background:var(--paper); border:2px solid var(--line-soft); font-size:{pick('18px','16px')}; }}
    .volume-chip b {{ color:var(--accent); font-size:22px; }} .volume-chip span {{ align-self:center; }} .volume-chip strong {{ grid-column:1/-1; color:var(--ink); }}
    .flow-grid {{ stroke:rgba(82,101,119,.35); stroke-width:3; }}
    .flow-block {{ transform-box:fill-box; transform-origin:left center; }}
    .flow-block rect {{ stroke:var(--ink); stroke-width:3; }} .flow-block.process-0 rect {{ fill:rgba(233,121,50,.30); }} .flow-block.process-1 rect {{ fill:rgba(82,101,119,.20); }} .flow-block.process-2 rect {{ fill:rgba(185,84,27,.18); }}
    .flow-block text,.flow-process,.flow-time {{ fill:var(--ink); font-size:21px; font-weight:800; }} .flow-time {{ fill:var(--steel); }}
    .flow-metrics {{ display:flex; flex-wrap:wrap; justify-content:center; gap:12px; }} .flow-metrics span {{ padding:10px 15px; border-radius:999px; border:2px solid var(--steel); background:var(--paper); font-size:{pick('19px','17px')}; }}

    /* Rebar length */
    .rebar-seg {{ fill:none; stroke:var(--ink); stroke-width:14; stroke-linecap:round; }}
    .rebar-bend circle {{ fill:rgba(233,121,50,.14); stroke:var(--accent); stroke-width:3; }}
    .rebar-bend text {{ fill:var(--accent); font-size:15px; font-weight:800; }}
    .rebar-dim {{ fill:var(--steel); font-size:21px; font-weight:700; }}
    .rebar-bar-title {{ fill:var(--steel); font-size:20px; font-weight:700; }}
    .rebar-bar {{ transform-box:fill-box; transform-origin:left center; }}
    .rebar-bar rect {{ stroke:var(--ink); stroke-width:2.5; }}
    .rebar-bar.part-0 rect {{ fill:rgba(233,121,50,.30); }} .rebar-bar.part-1 rect {{ fill:rgba(82,101,119,.22); }} .rebar-bar.part-2 rect {{ fill:rgba(185,84,27,.20); }}
    .rebar-bar text {{ fill:var(--ink); font-size:19px; font-weight:800; }}

    /* Earned value */
    .ev-axis {{ stroke:var(--ink); stroke-width:5; }}
    .ev-tick {{ fill:var(--steel); font-size:20px; font-weight:700; }}
    .ev-line {{ fill:none; stroke-width:7; stroke-linecap:round; stroke-linejoin:round; }}
    .ev-line.pv {{ stroke:var(--steel); stroke-dasharray:16 12; }}
    .ev-line.ev {{ stroke:var(--accent-bright); }}
    .ev-line.ac {{ stroke:var(--danger); }}
    .ev-legend text {{ fill:var(--ink); font-size:19px; font-weight:700; }}
    .ev-legend .lg.pv {{ fill:var(--steel); }} .ev-legend .lg.ev {{ fill:var(--accent-bright); }} .ev-legend .lg.ac {{ fill:var(--danger); }}
    .ev-gap path {{ fill:none; stroke:var(--ink); stroke-width:3.5; }}
    .ev-gap text {{ fill:var(--ink); font-size:21px; font-weight:800; }}
    .ev-gap.cv text {{ fill:var(--danger); }} .ev-gap.sv text {{ fill:var(--accent); }}
    .ev-chips {{ display:flex; flex-wrap:wrap; gap:12px; justify-content:center; }}
    .ev-chip {{ padding:10px 16px; border-radius:999px; border:2px solid var(--steel); background:var(--paper); font-size:{pick('19px','17px')}; font-weight:700; }}

    /* Projection system */
    .proj-plane {{ fill:none; stroke:var(--ink); stroke-width:3.5; stroke-linejoin:round; }}
    .proj-axis {{ stroke:var(--steel); stroke-width:2.5; }}
    .proj-axis-label {{ fill:var(--steel); font-size:23px; font-weight:700; font-style:italic; }}
    .proj-plane-letter {{ fill:var(--ink); font-size:31px; font-weight:800; }}
    .proj-point circle {{ fill:var(--accent); }}
    .proj-point text {{ fill:var(--accent); font-size:27px; font-weight:800; }}
    .proj-ray {{ fill:none; stroke:var(--accent-bright); stroke-width:3; stroke-dasharray:8 7; }}
    .proj-foot circle {{ fill:var(--ink); }}
    .proj-foot text {{ fill:var(--ink); font-size:24px; font-weight:800; }}
    .proj-arrow {{ fill:none; stroke:var(--accent); stroke-width:3.5; }}
    .proj-arrow-head {{ fill:var(--accent); }}
    .proj-arrow-label {{ fill:var(--accent); font-size:20px; font-weight:700; }}
    .proj-result {{ color:var(--accent); font:800 {pick('40px','35px')}/1.1 "Songti SC",serif; }}
    """


TIMELINE_JS = r"""
    window.__timelines = window.__timelines || {};
    const tl = gsap.timeline({paused:true});
    const WIDTH = __WIDTH__;
    const HEIGHT = __HEIGHT__;
    const SEGMENTS = __SEGMENTS__;
    const subLayer = document.getElementById("subtitle-layer");

    function drawIn(el, time, dur) {
      const length = Math.ceil(el.getTotalLength ? el.getTotalLength() : 0);
      if (!length) { tl.fromTo(el, {opacity:0}, {opacity:1, duration:.4}, time); return; }
      el.style.strokeDasharray = length;
      tl.fromTo(el, {strokeDashoffset:length}, {strokeDashoffset:0, duration:dur, ease:"power2.inOut"}, time);
    }

    function animateEl(el, style, time) {
      switch (style) {
        case "draw": drawIn(el, time, .7); break;
        case "pop": tl.fromTo(el, {scale:.4, opacity:0, transformOrigin:"50% 50%", transformBox:"fill-box"}, {scale:1, opacity:1, duration:.5, ease:"back.out(1.4)"}, time); break;
        case "rise": tl.fromTo(el, {y:26, opacity:0}, {y:0, opacity:1, duration:.5, ease:"power3.out"}, time); break;
        case "fade": tl.fromTo(el, {opacity:0}, {opacity:1, duration:.4, ease:"sine.out"}, time); break;
        case "grow-y": tl.fromTo(el, {scaleY:0, opacity:0}, {scaleY:1, opacity:1, duration:.55, ease:"back.out(1.2)"}, time); break;
        case "grow-x": tl.fromTo(el, {scaleX:0, opacity:0}, {scaleX:1, opacity:1, duration:.45, ease:"power2.out"}, time); break;
        case "highlight":
          if (el.getAttribute("data-hl") === "fill") {
            tl.to(el, {fill:"#B9541B", duration:.42, ease:"power2.out"}, time);
          } else {
            tl.to(el, {stroke:"#B9541B", strokeWidth:"+=3", duration:.42, ease:"power2.out"}, time);
          }
          break;
        default: tl.fromTo(el, {opacity:0}, {opacity:1, duration:.4}, time);
      }
    }

    SEGMENTS.forEach((seg, index) => {
      const n = index + 1, t = seg.start, D = seg.duration;
      const scene = document.getElementById("s" + n);
      const continueMode = seg.mode === "continue";

      // Furniture
      const topline = scene.querySelector(".topline");
      const rail = scene.querySelector(".progress-rail");
      const panel = scene.querySelector(".visual-panel");
      const card = scene.querySelector(".knowledge-card");
      const underline = scene.querySelector(".headline-line");
      const source = scene.querySelector(".source-label");
      const grid = scene.querySelector(".paper-grid");
      const ghost = scene.querySelector(".ghost-num");
      const ring = scene.querySelector(".corner-ring");

      if (!continueMode) {
        tl.fromTo(topline, {y:-16, opacity:0}, {y:0, opacity:1, duration:.45, ease:"power2.out"}, t + .1);
        tl.fromTo(rail, {opacity:0}, {opacity:1, duration:.4}, t + .15);
        tl.fromTo(panel, {y:30, opacity:0}, {y:0, opacity:1, duration:.6, ease:"power3.out"}, t + .2);
        tl.fromTo(source, {opacity:0}, {opacity:1, duration:.4}, t + Math.min(1.1, D * .2));
      }
      tl.fromTo(card, {x:__CARD_X__, opacity:0}, {x:0, opacity:1, duration:.55, ease:"power3.out"}, t + (continueMode ? .15 : .4));
      tl.fromTo(underline, {scaleX:0}, {scaleX:1, duration:.45, ease:"power2.out"}, t + (continueMode ? .5 : .8));
      if (continueMode) tl.fromTo(source, {opacity:0}, {opacity:1, duration:.35}, t + .5);

      // Slow ambient motion across the full scene keeps frames alive.
      tl.fromTo(grid, {x:0, y:0}, {x:-22, y:-15, duration:D, ease:"none"}, t);
      tl.fromTo(ghost, {y:0}, {y:-14, duration:D, ease:"none"}, t);
      tl.fromTo(ring, {rotation:0}, {rotation:9, duration:D, ease:"none"}, t);
      const fill = scene.querySelector(".rail-fill");
      if (fill) tl.fromTo(fill, {scaleX:0}, {scaleX:1, duration:D, ease:"none"}, t);

      // Beat-scheduled content groups
      (seg.groups || []).forEach((g) => {
        const els = scene.querySelectorAll('[data-anim="' + g.name + '"],[data-anim2="' + g.name + '"]');
        if (!els.length) return;
        const groupStart = t + Math.max(.3, Math.min(g.at * D, D - 1.0));
        let per = (g.per || 0) * D;
        if (els.length > 1) per = Math.min(per, (t + D * .9 - groupStart) / els.length);
        els.forEach((el, i) => animateEl(el, g.style, groupStart + i * Math.max(per, 0)));
      });

      // Sentence-level subtitles
      (seg.subs || []).forEach((chunk, ci) => {
        const sub = document.createElement("div");
        sub.className = "subtitle"; sub.id = "sub-" + n + "-" + ci; sub.textContent = chunk.text;
        subLayer.appendChild(sub);
        tl.fromTo(sub, {y:14, opacity:0}, {y:0, opacity:1, duration:.24, ease:"power2.out"}, chunk.in);
        tl.to(sub, {opacity:0, duration:.15, ease:"power1.in"}, Math.max(chunk.out - .15, chunk.in + .4));
        tl.set(sub, {visibility:"hidden"}, chunk.out);
      });
    });

    // Scene transitions (entry transition of each scene)
    for (let i = 1; i < SEGMENTS.length; i++) {
      const prev = SEGMENTS[i - 1], cur = SEGMENTS[i], t = cur.start;
      tl.set(cur.sel, {display:"block", zIndex:3}, t);
      if (cur.entry === "hold") {
        // Continue scenes share identical static graphics: a hard cut is seamless
        // and avoids a cross-fade window where duplicate text overlaps.
        tl.set(cur.sel, {opacity:1}, t);
        tl.set(prev.sel, {display:"none"}, t);
      } else if (cur.entry === "blur-crossfade") {
        tl.fromTo(cur.sel, {opacity:0}, {opacity:1, duration:.55, ease:"power1.inOut"}, t);
        tl.fromTo(prev.sel, {filter:"blur(0px)"}, {filter:"blur(9px)", duration:.55, ease:"power1.in"}, t);
        tl.set(prev.sel, {display:"none"}, t + .6);
      } else if (cur.entry === "push-up") {
        tl.to(prev.sel, {y:-HEIGHT, duration:.5, ease:"power3.inOut"}, t);
        tl.fromTo(cur.sel, {y:HEIGHT, opacity:1}, {y:0, duration:.5, ease:"power3.inOut"}, t);
        tl.set(prev.sel, {display:"none"}, t + .55);
      } else {
        tl.to(prev.sel, {x:-WIDTH, duration:.5, ease:"power3.inOut"}, t);
        tl.fromTo(cur.sel, {x:WIDTH, opacity:1}, {x:0, duration:.5, ease:"power3.inOut"}, t);
        tl.set(prev.sel, {display:"none"}, t + .55);
      }
      tl.set(cur.sel, {zIndex:1}, t + .7);
    }
    window.__timelines["main"] = tl;
"""


def build_html(project: dict, storyboard: dict, timeline: dict, profile: str, include_audio: bool) -> str:
    width, height = PROFILES[profile]
    segments = storyboard["segments"]
    timeline_by_id = {row["id"]: row for row in timeline["segments"]}
    rows = [timeline_by_id[segment["id"]] for segment in segments]
    label_parts = (
        str(project.get("exam_track_label", "")),
        str(project.get("subject", "")),
        str(project.get("exam_year", "")),
    )
    project_label = "｜".join(part for part in label_parts if part)
    # Keep the brand subline on one physical line: the header row has limited
    # width (especially vertical), so elide the subject part when the combined
    # label would overflow instead of letting the text clip or wrap.
    label_limit = 22 if profile == "vertical" else 40
    if len(project_label) > label_limit:
        track, subject, year = label_parts
        fixed = len(track) + len(year) + 2
        room = max(4, label_limit - fixed - 1)
        subject = subject[:room] + "…"
        project_label = "｜".join(part for part in (track, subject, year) if part)
    total = len(segments)
    scenes = "".join(
        scene_markup(segment, index, total, rows, project_label).replace("\n", "")
        for index, segment in enumerate(segments, start=1)
    )
    audio_tags = []
    if include_audio:
        for row in rows:
            audio_tags.append(
                f'<audio id="a{row["id"]}" src="audio/seg-{int(row["id"]):02d}.mp3" '
                f'data-start="{row["audio_start"]}" data-duration="{row["audio_duration"]}" data-track-index="2"></audio>'
            )

    timeline_entries = []
    for index, (segment, row) in enumerate(zip(segments, rows), start=1):
        anim = segment.get("animation") or {}
        mode = anim.get("mode", "build")
        if index == 1:
            entry = "none"
        elif mode == "continue":
            entry = "hold"
        else:
            entry = segments[index - 2].get("transition", "blur-crossfade")
            if entry not in TRANSITIONS:
                entry = "blur-crossfade"
        timeline_entries.append(
            {
                "sel": f"#s{index}",
                "start": row["start"],
                "duration": row["duration"],
                "mode": mode,
                "entry": entry,
                "groups": schedule_groups(segment),
                "subs": subtitle_windows(row),
            }
        )
    timeline_js = json.dumps(timeline_entries, ensure_ascii=False)
    card_x = "-46" if profile == "vertical" else "58"
    script = (
        TIMELINE_JS
        .replace("__WIDTH__", str(width))
        .replace("__HEIGHT__", str(height))
        .replace("__SEGMENTS__", timeline_js)
        .replace("__CARD_X__", card_x)
    )
    gsap_src = "gsap.min.js" if GSAP_VENDOR.exists() else "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <script src="{gsap_src}"></script>
  <style>{build_css(profile)}</style>
</head>
<body>
  <div id="root" data-composition-id="main" data-width="{width}" data-height="{height}" data-start="0" data-duration="{timeline['total']}">
    {scenes}
    <div id="subtitle-layer"></div>
    {' '.join(audio_tags)}
  </div>
  <script>{script}</script>
</body>
</html>
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir")
    parser.add_argument("--profile", choices=("all", *PROFILES), default="all")
    args = parser.parse_args()

    root = Path(args.project_dir).expanduser().resolve()
    project = read_json(root / "project.json")
    storyboard = read_json(root / "content/storyboard.json")
    segments = storyboard.get("segments", [])
    if not 5 <= len(segments) <= 9:
        die(f"storyboard must contain 5-9 segments, got {len(segments)}")
    ids = [item.get("id") for item in segments]
    if ids != list(range(1, len(segments) + 1)):
        die(f"segment IDs must be continuous from 1: {ids}")
    for index, segment in enumerate(segments):
        visual_type = segment.get("visual_type", "")
        if visual_type in DYNAMIC_DATA_KEYS:
            dynamic_data(segment)  # dies when the data block is missing
        anim = segment.get("animation") or {}
        if anim.get("mode") == "continue":
            if index == 0:
                die("segment 1 cannot use animation.mode=continue")
            if segments[index - 1].get("visual_type") != visual_type:
                die(
                    f"segment {segment.get('id')} uses continue mode but previous segment has a "
                    f"different visual_type; static graphics would jump"
                )

    duration_path = root / "audio/durations.json"
    timeline = read_json(duration_path) if duration_path.exists() else estimated_timeline(segments)
    if len(timeline.get("segments", [])) != len(segments):
        die("audio timeline segment count does not match storyboard")

    include_audio = all((root / "audio" / f"seg-{int(item['id']):02d}.mp3").exists() for item in segments)
    profiles = PROFILES if args.profile == "all" else {args.profile: PROFILES[args.profile]}
    for profile in profiles:
        output = root / "composition" / profile / "index.html"
        output.parent.mkdir(parents=True, exist_ok=True)
        if include_audio:
            composition_audio = output.parent / "audio"
            composition_audio.mkdir(parents=True, exist_ok=True)
            for item in segments:
                source_audio = root / "audio" / f"seg-{int(item['id']):02d}.mp3"
                shutil.copy2(source_audio, composition_audio / source_audio.name)
        if GSAP_VENDOR.exists():
            shutil.copy2(GSAP_VENDOR, output.parent / "gsap.min.js")
        else:
            print("WARN: assets/vendor/gsap.min.js missing; composition falls back to the GSAP CDN")
        output.write_text(build_html(project, storyboard, timeline, profile, include_audio), encoding="utf-8")
        print(f"Generated {profile}: {output}")
    if timeline.get("preview_timing"):
        print("WARN: audio/durations.json is missing; compositions use estimated preview timing")
    if not include_audio:
        print("WARN: one or more audio segments are missing; generated compositions are silent previews")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
