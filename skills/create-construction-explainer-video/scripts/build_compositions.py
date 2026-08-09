#!/usr/bin/env python3
"""Build deterministic HyperFrames HTML compositions for vertical and landscape video."""

from __future__ import annotations

import argparse
import html
import json
import math
import shutil
import sys
from pathlib import Path


PROFILES = {"vertical": (1080, 1920), "landscape": (1920, 1080)}


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


def estimated_timeline(segments: list[dict]) -> dict:
    cursor = 0.0
    rows = []
    for segment in segments:
        narration = str(segment.get("narration", ""))
        estimate = max(float(segment.get("min_duration", 5.5)), len(narration) / 4.5 + 1.55)
        duration = round(estimate, 3)
        rows.append(
            {
                "id": segment["id"],
                "title": segment.get("title", ""),
                "file": f"audio/seg-{int(segment['id']):02d}.mp3",
                "audio_duration": max(0.0, round(duration - 1.55, 3)),
                "start": round(cursor, 3),
                "audio_start": round(cursor + 0.65, 3),
                "duration": duration,
                "subtitle": narration,
            }
        )
        cursor += duration
    return {"total": round(cursor, 3), "segments": rows, "preview_timing": True}


def network_plan_markup(segment: dict) -> str:
    network = segment.get("network") or {}
    nodes = network.get("nodes") or [
        {"id": 1, "x": 90, "y": 280},
        {"id": 2, "x": 300, "y": 150},
        {"id": 3, "x": 300, "y": 410},
        {"id": 4, "x": 560, "y": 150},
        {"id": 5, "x": 560, "y": 410},
        {"id": 6, "x": 810, "y": 280},
    ]
    activities = network.get("activities") or []
    by_id = {str(node.get("id")): node for node in nodes}
    edges = []
    labels = []
    for activity in activities:
        start = by_id.get(str(activity.get("from")))
        end = by_id.get(str(activity.get("to")))
        if not start or not end:
            continue
        x1, y1 = float(start.get("x", 0)), float(start.get("y", 0))
        x2, y2 = float(end.get("x", 0)), float(end.get("y", 0))
        dx, dy = x2 - x1, y2 - y1
        distance = max(math.hypot(dx, dy), 1.0)
        ux, uy = dx / distance, dy / distance
        sx, sy = x1 + ux * 39, y1 + uy * 39
        ex, ey = x2 - ux * 45, y2 - uy * 45
        critical = " critical-activity" if activity.get("critical") else ""
        arrow_tip_x, arrow_tip_y = ex, ey
        arrow_base_x, arrow_base_y = ex - ux * 18, ey - uy * 18
        px, py = -uy * 9, ux * 9
        edges.append(
            f'<path class="draw network-activity{critical}" d="M {sx:.1f} {sy:.1f} L {ex:.1f} {ey:.1f}" />'
            f'<polygon class="network-arrow{critical}" points="{arrow_tip_x:.1f},{arrow_tip_y:.1f} {arrow_base_x + px:.1f},{arrow_base_y + py:.1f} {arrow_base_x - px:.1f},{arrow_base_y - py:.1f}" />'
        )
        label = e(activity.get("label", ""))
        duration = e(activity.get("duration", ""))
        text = " · ".join(item for item in (label, f"{duration}天" if duration else "") if item)
        mx, my = (sx + ex) / 2, (sy + ey) / 2 - 14
        labels.append(
            f'<g class="network-label" transform="translate({mx:.1f} {my:.1f})"><rect x="-46" y="-21" width="92" height="34" rx="17"/><text text-anchor="middle" y="4">{text}</text></g>'
        )
    node_groups = []
    for node in nodes:
        node_id = e(node.get("id", ""))
        x, y = float(node.get("x", 0)), float(node.get("y", 0))
        early, late = node.get("early"), node.get("late")
        time_text = ""
        if early is not None or late is not None:
            time_text = f'<text class="node-time" text-anchor="middle" y="68">早 {e(early if early is not None else "—")} ｜ 迟 {e(late if late is not None else "—")}</text>'
        node_groups.append(
            f'<g class="network-node" transform="translate({x:.1f} {y:.1f})"><circle r="36"/><text text-anchor="middle" y="10">{node_id}</text>{time_text}</g>'
        )
    metrics = network.get("metrics") or []
    metric_html = "".join(f'<span class="metric-chip">{e(item)}</span>' for item in metrics[:4])
    return f'''<div class="network-visual">
      <svg viewBox="0 0 900 560" aria-label="双代号网络计划动态图">
        {''.join(edges)}
        {''.join(labels)}
        {''.join(node_groups)}
      </svg>
      <div class="metric-row">{metric_html}</div>
    </div>'''


def earthwork_markup(segment: dict) -> str:
    geometry = segment.get("geometry") or {}
    bottom_length = float(geometry.get("bottom_length", 12))
    bottom_width = float(geometry.get("bottom_width", 8))
    depth = float(geometry.get("depth", 3))
    slope = float(geometry.get("slope", 0.5))
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
    step_html = "".join(f'<div class="formula-stage"><span>{index}</span>{e(item)}</div>' for index, item in enumerate(formula_steps, start=1))
    return f'''<div class="earthwork-visual">
      <svg viewBox="0 0 900 560" aria-label="放坡基坑土方几何计算动态图">
        <g class="earth-section">
          <path class="draw earth-surface" d="M45 118 H425" />
          <path class="earth-cut" d="M88 118 L165 430 H305 L382 118 Z" />
          <path class="draw earth-outline" d="M88 118 L165 430 H305 L382 118" />
          <path class="draw dimension" d="M70 118 V430 M58 118 H82 M58 430 H82" />
          <text class="dimension-label" x="34" y="282" text-anchor="middle" transform="rotate(-90 34 282)">深 {depth:g} m</text>
          <path class="draw dimension" d="M165 466 H305 M165 454 V478 M305 454 V478" />
          <text class="dimension-label" x="235" y="510" text-anchor="middle">底宽 {bottom_width:g} m</text>
          <path class="draw dimension" d="M88 82 H382 M88 70 V94 M382 70 V94" />
          <text class="dimension-label" x="235" y="55" text-anchor="middle">顶宽 {top_width:g} m</text>
          <text class="slope-label" x="342" y="270">放坡 {slope:g} : 1</text>
        </g>
        <g class="earth-plan" transform="translate(505 120)">
          <rect class="plan-top" x="0" y="0" width="330" height="250" rx="8" />
          <rect class="plan-mid" x="35" y="30" width="260" height="190" rx="6" />
          <rect class="plan-bottom" x="70" y="60" width="190" height="130" rx="4" />
          <text x="165" y="-26" text-anchor="middle">平面三截面</text>
          <text x="165" y="78" text-anchor="middle">底 {bottom_length:g} × {bottom_width:g}</text>
          <text x="165" y="120" text-anchor="middle">中 {mid_length:g} × {mid_width:g}</text>
          <text x="165" y="162" text-anchor="middle">顶 {top_length:g} × {top_width:g}</text>
        </g>
      </svg>
      <div class="formula-stages">{step_html}</div>
    </div>'''


def cashflow_markup(segment: dict) -> str:
    data = segment.get("cashflow") or {}
    flows = data.get("flows") or [-1000, 300, 400, 450, 350]
    rate = float(data.get("rate", 0.08))
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
        arrows.append(f'<line class="cash-arrow {css}" x1="{x:.1f}" y1="{baseline}" x2="{x:.1f}" y2="{end_y:.1f}" />')
        direction = -1 if value >= 0 else 1
        points = f"{x:.1f},{end_y:.1f} {x-10:.1f},{end_y+direction*18:.1f} {x+10:.1f},{end_y+direction*18:.1f}"
        arrows.append(f'<polygon class="cash-head {css}" points="{points}" />')
        labels.append(f'<text class="cash-label" x="{x:.1f}" y="{end_y + (-20 if value >= 0 else 34):.1f}" text-anchor="middle">{value:g}</text>')
        labels.append(f'<text class="cash-period" x="{x + 24:.1f}" y="302" text-anchor="middle">{index}</text>')
        discounted.append(value / ((1 + rate) ** index))
    npv = sum(discounted)
    rows = "".join(
        f'<span class="discount-chip">第{index}期：{value:.2f}</span>'
        for index, value in enumerate(discounted[:5])
    )
    return f'''<div class="cashflow-visual">
      <svg viewBox="0 0 900 520" aria-label="现金流量与净现值动态图">
        <path class="draw cash-axis" d="M55 270 H850" />
        {''.join(arrows)}
        {''.join(labels)}
        <text class="cash-rate" x="450" y="470" text-anchor="middle">折现率 i = {rate * 100:g}%</text>
      </svg>
      <div class="discount-row">{rows}</div>
      <div class="cash-result">NPV = {npv:.2f}</div>
    </div>'''


def component_volume_markup(segment: dict) -> str:
    data = segment.get("component_volume") or {}
    components = data.get("components") or [
        {"label": "柱", "formula": "4×0.4×0.4×3", "volume": 1.92},
        {"label": "梁", "formula": "4×5×0.3×0.5", "volume": 3.0},
        {"label": "板", "formula": "6×5×0.12", "volume": 3.6},
    ]
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
        blocks.append(f'<g class="volume-block {css}" transform="translate({x} {y})">{shape}<text x="45" y="118" text-anchor="middle">{label}</text></g>')
        chips.append(f'<div class="volume-chip"><b>{label}</b><span>{formula}</span><strong>{volume:g} m³</strong></div>')
    total = sum(float(item.get("volume", 0)) for item in components[:3])
    return f'''<div class="component-volume-visual">
      <svg viewBox="0 0 900 520" aria-label="梁板柱构件体积拆分动态图">
        <path class="draw volume-base" d="M55 410 H845" />
        {''.join(blocks)}
      </svg>
      <div class="volume-chips">{''.join(chips)}</div>
      <div class="volume-total">合计 {total:g} m³</div>
    </div>'''


def flow_schedule_markup(segment: dict) -> str:
    data = segment.get("flow_schedule") or {}
    sections = int(data.get("sections", 4))
    processes = data.get("processes") or ["A", "B", "C"]
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
        grid.append(f'<path class="draw flow-grid" d="M{x:.1f} {top} V{top + row_height * len(processes)}" />')
        labels.append(f'<text class="flow-time" x="{x:.1f}" y="{top - 24}" text-anchor="middle">{tick * rhythm:g}</text>')
    for row, process in enumerate(processes):
        y = top + row * row_height
        labels.append(f'<text class="flow-process" x="65" y="{y + 62}" text-anchor="middle">{e(process)}</text>')
        for section in range(sections):
            x = left + (row + section) * unit_width + 5
            blocks.append(f'<g class="flow-block process-{row}" transform="translate({x:.1f} {y + 15:.1f})"><rect width="{unit_width - 10:.1f}" height="72" rx="12"/><text x="{(unit_width - 10)/2:.1f}" y="46" text-anchor="middle">{section + 1}段</text></g>')
    grid.append(f'<path class="draw flow-grid" d="M{left} {top + row_height * len(processes)} H{left + plot_width}" />')
    return f'''<div class="flow-schedule-visual">
      <svg viewBox="0 0 900 520" aria-label="等节奏流水施工进度动态图">
        {''.join(grid)}
        {''.join(blocks)}
        {''.join(labels)}
      </svg>
      <div class="flow-metrics"><span>施工段 m={sections}</span><span>过程 n={len(processes)}</span><span>节拍 K={rhythm:g}天</span></div>
      <div class="flow-result">T = (m+n-1)K = {total:g}天</div>
    </div>'''


def visual_markup(segment: dict) -> str:
    visual_type = segment.get("visual_type", "concept")
    bullets = [e(item) for item in segment.get("bullets", []) if str(item).strip()]
    steps = [e(item) for item in segment.get("steps", []) if str(item).strip()]
    key_number = e(segment.get("key_number", ""))
    formula = e(segment.get("formula", ""))

    if visual_type == "network-plan":
        return network_plan_markup(segment)

    if visual_type == "earthwork-volume":
        return earthwork_markup(segment)

    if visual_type == "cashflow":
        return cashflow_markup(segment)

    if visual_type == "component-volume":
        return component_volume_markup(segment)

    if visual_type == "flow-schedule":
        return flow_schedule_markup(segment)

    if visual_type in {"process", "timeline"}:
        items = steps or bullets or ["前置条件", "关键工序", "检查验收"]
        cards = []
        for index, item in enumerate(items[:5], start=1):
            cards.append(f'<div class="step"><span>{index:02d}</span><strong>{item}</strong></div>')
        return '<div class="step-flow">' + '<i class="flow-line"></i>'.join(cards) + "</div>"

    if visual_type == "comparison":
        comparison = segment.get("comparison") or {}
        left_title = e(comparison.get("left_title", "正确做法"))
        right_title = e(comparison.get("right_title", "常见错误"))
        left = comparison.get("left") or bullets[:2] or ["按设计与现行口径执行"]
        right = comparison.get("right") or bullets[2:4] or ["省略条件或混淆顺序"]
        left_items = "".join(f"<li>{e(item)}</li>" for item in left)
        right_items = "".join(f"<li>{e(item)}</li>" for item in right)
        return (
            '<div class="comparison">'
            f'<section class="good"><b>{left_title}</b><ul>{left_items}</ul></section>'
            f'<section class="bad"><b>{right_title}</b><ul>{right_items}</ul></section>'
            "</div>"
        )

    if visual_type == "calculation":
        items = steps or bullets or ["列出条件", "统一单位", "代入复算"]
        return (
            '<div class="calculation">'
            f'<div class="formula">{formula or "公式与单位"}</div>'
            + "".join(f'<div class="calc-step"><span>{i}</span>{item}</div>' for i, item in enumerate(items[:4], start=1))
            + (f'<div class="key-number">{key_number}</div>' if key_number else "")
            + "</div>"
        )

    if visual_type == "summary":
        pills = bullets or steps or ["条件", "顺序", "检查", "来源"]
        return (
            '<div class="summary-visual">'
            f'<div class="key-number">{key_number or "记条件 · 记顺序"}</div>'
            f'<div class="pill-row">{"".join(f"<span>{item}</span>" for item in pills[:5])}</div>'
            "</div>"
        )

    return f'''<div class="concept-visual">
      <svg viewBox="0 0 760 520" aria-hidden="true">
        <path class="draw" d="M120 420V175L375 65l265 110v245" />
        <path class="draw secondary" d="M170 420V210h410v210M260 420V265h95v155M430 420V265h95v155" />
        <path class="draw accent" d="M85 420h590M210 154l165-72 170 72" />
        <circle class="pulse" cx="375" cy="235" r="44" />
        <path class="accent-arrow" d="M375 188v94m-18-20 18 20 18-20" />
      </svg>
      {f'<div class="key-number">{key_number}</div>' if key_number else ''}
    </div>'''


def scene_markup(segment: dict, index: int) -> str:
    bullets = [item for item in segment.get("bullets", []) if str(item).strip()]
    bullet_html = "".join(f"<li>{e(item)}</li>" for item in bullets[:4])
    source_label = e(segment.get("source_label", "来源见证据包"))
    return f'''<section class="scene" id="s{index}">
      <div class="paper-grid"></div>
      <div class="scene-number" aria-hidden="true" data-layout-ignore></div>
      <header class="topline">
        <span class="brand" data-layout-allow-overflow data-layout-allow-overlap>建知课</span>
        <span class="section-tag">{e(segment.get('title', f'场景 {index}'))}</span>
      </header>
      <main class="main-grid">
        <div class="visual-panel">{visual_markup(segment)}</div>
        <article class="knowledge-card">
          <p class="eyebrow">{e(segment.get('title', '核心知识'))}</p>
          <h1>{e(segment.get('headline', segment.get('title', '核心知识')))}</h1>
          <ul>{bullet_html}</ul>
        </article>
      </main>
      <footer class="source-label">{source_label}</footer>
    </section>'''


def build_html(project: dict, storyboard: dict, timeline: dict, profile: str, include_audio: bool) -> str:
    width, height = PROFILES[profile]
    segments = storyboard["segments"]
    timeline_by_id = {row["id"]: row for row in timeline["segments"]}
    rows = [timeline_by_id[segment["id"]] for segment in segments]
    scenes = "".join(scene_markup(segment, index).replace("\n", "") for index, segment in enumerate(segments, start=1))
    audio_tags = []
    if include_audio:
        for row in rows:
            audio_tags.append(
                f'<audio id="a{row["id"]}" src="audio/seg-{int(row["id"]):02d}.mp3" '
                f'data-start="{row["audio_start"]}" data-duration="{row["audio_duration"]}" data-track-index="2"></audio>'
            )
    timeline_js = json.dumps(
        [
            {
                "sel": f"#s{index}",
                "start": row["start"],
                "duration": row["duration"],
                "subtitle": row["subtitle"],
                "transition": segments[index - 1].get("transition", "blur-crossfade"),
            }
            for index, row in enumerate(rows, start=1)
        ],
        ensure_ascii=False,
    )
    project_label = "｜".join(
        [str(project.get("exam_track_label", "")), str(project.get("subject", "")), str(project.get("exam_year", ""))]
    )
    vertical = profile == "vertical"
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <style>
    @font-face {{ font-family: "PingFang SC"; src: local("PingFang SC"); }}
    @font-face {{ font-family: "Songti SC"; src: local("Songti SC"); }}
    @font-face {{ font-family: "Noto Sans CJK SC"; src: local("Noto Sans CJK SC"); }}
    :root {{ --bg:#F3F0E8; --ink:#24313F; --accent:#B9541B; --accent-bright:#E97932; --steel:#526577; --paper:#FCFAF5; --danger:#A9342D; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ width:{width}px; height:{height}px; overflow:hidden; background:var(--bg); color:var(--ink); font-family:"PingFang SC","Noto Sans CJK SC",sans-serif; }}
    #root {{ position:relative; width:{width}px; height:{height}px; overflow:hidden; }}
    .scene {{ position:absolute; inset:0; overflow:hidden; background:var(--bg); }}
    .scene + .scene {{ opacity:0; display:none; }}
    .paper-grid {{ position:absolute; inset:0; opacity:.4; background-image:linear-gradient(rgba(102,119,137,.10) 1px,transparent 1px),linear-gradient(90deg,rgba(102,119,137,.10) 1px,transparent 1px); background-size:{'54px 54px' if vertical else '64px 64px'}; }}
    .scene-number {{ position:absolute; right:{'-80px' if vertical else '-40px'}; bottom:{'180px' if vertical else '-110px'}; width:{'390px' if vertical else '360px'}; height:{'390px' if vertical else '360px'}; border:44px double rgba(82,101,119,.10); border-radius:50%; }}
    .topline {{ position:absolute; z-index:4; left:{'56px' if vertical else '84px'}; right:{'56px' if vertical else '84px'}; top:{'70px' if vertical else '50px'}; display:flex; justify-content:space-between; align-items:center; font-size:{'30px' if vertical else '26px'}; }}
    .brand {{ color:var(--accent); font-weight:800; letter-spacing:.2em; }}
    .section-tag {{ color:var(--steel); border-bottom:3px solid rgba(102,119,137,.3); padding-bottom:10px; }}
    .main-grid {{ position:absolute; z-index:2; left:{'56px' if vertical else '84px'}; right:{'56px' if vertical else '84px'}; top:{'165px' if vertical else '135px'}; bottom:{'260px' if vertical else '175px'}; display:grid; grid-template-columns:{'1fr' if vertical else '1.25fr .9fr'}; grid-template-rows:{'1.15fr .85fr' if vertical else '1fr'}; gap:{'42px' if vertical else '64px'}; align-items:stretch; }}
    .visual-panel {{ min-height:0; display:flex; align-items:center; justify-content:center; border:2px solid rgba(102,119,137,.18); border-radius:32px; background:rgba(252,250,245,.58); padding:{'30px' if vertical else '38px'}; overflow:hidden; }}
    .knowledge-card {{ align-self:center; background:rgba(252,250,245,.94); border-left:10px solid var(--accent); border-radius:28px; padding:{'42px 44px' if vertical else '48px 50px'}; box-shadow:0 24px 70px rgba(36,49,63,.12); }}
    .eyebrow {{ color:var(--accent); font-weight:800; letter-spacing:.18em; font-size:{'25px' if vertical else '22px'}; margin-bottom:20px; }}
    h1 {{ font-family:"Songti SC",serif; font-size:{'62px' if vertical else '60px'}; line-height:1.18; margin-bottom:30px; }}
    .knowledge-card ul {{ list-style:none; display:grid; gap:18px; }}
    .knowledge-card li {{ font-size:{'31px' if vertical else '29px'}; line-height:1.45; padding-left:34px; position:relative; }}
    .knowledge-card li::before {{ content:""; position:absolute; left:0; top:.55em; width:13px; height:13px; border-radius:50%; background:var(--accent); }}
    .source-label {{ visibility:hidden; position:absolute; z-index:4; left:{'56px' if vertical else '84px'}; bottom:{'236px' if vertical else '126px'}; font-size:{'21px' if vertical else '18px'}; color:var(--steel); max-width:70%; }}
    #subtitle-layer {{ position:absolute; z-index:20; left:{'50px' if vertical else '240px'}; right:{'50px' if vertical else '240px'}; bottom:{'68px' if vertical else '35px'}; height:{'104px' if vertical else '72px'}; display:flex; align-items:center; justify-content:center; }}
    .subtitle {{ position:absolute; opacity:0; max-width:100%; color:white; background:rgba(36,49,63,.92); border-radius:18px; padding:{'20px 30px' if vertical else '14px 28px'}; font-size:{'34px' if vertical else '30px'}; line-height:1.45; text-align:center; }}
    .concept-visual,.summary-visual,.calculation {{ width:100%; height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:24px; }}
    .concept-visual svg {{ width:100%; height:78%; overflow:visible; }}
    .draw {{ fill:none; stroke:var(--ink); stroke-width:8; stroke-linecap:round; stroke-linejoin:round; }}
    .draw.secondary {{ stroke:var(--steel); stroke-width:6; }} .draw.accent,.accent-arrow {{ fill:none; stroke:var(--accent); stroke-width:10; stroke-linecap:round; stroke-linejoin:round; }}
    .pulse {{ fill:rgba(233,121,50,.10); stroke:var(--accent); stroke-width:7; }}
    .key-number {{ font:800 {'70px' if vertical else '64px'}/1.1 "Songti SC",serif; color:var(--accent); text-align:center; }}
    .step-flow {{ width:100%; display:flex; flex-direction:{'column' if vertical else 'row'}; align-items:stretch; justify-content:center; gap:18px; }}
    .step {{ flex:1; min-height:{'108px' if vertical else '160px'}; display:flex; align-items:center; gap:22px; padding:24px; border-radius:22px; background:var(--paper); border:2px solid rgba(102,119,137,.25); font-size:{'27px' if vertical else '24px'}; }}
    .step span,.calc-step span {{ flex:none; width:48px; height:48px; border-radius:50%; display:grid; place-items:center; background:var(--accent); color:white; font-weight:800; }}
    .flow-line {{ flex:none; width:{'4px' if vertical else '36px'}; height:{'28px' if vertical else '4px'}; align-self:center; background:var(--accent); }}
    .comparison {{ width:100%; display:grid; grid-template-columns:1fr 1fr; gap:24px; }}
    .comparison section {{ min-height:330px; border-radius:26px; padding:32px; background:var(--paper); border-top:9px solid var(--accent); }}
    .comparison .bad {{ border-top-color:var(--danger); }} .comparison b {{ font-size:30px; }} .comparison ul {{ margin-top:24px; padding-left:28px; font-size:25px; line-height:1.55; }}
    .formula {{ padding:25px 35px; border:3px solid var(--accent); border-radius:20px; font:700 {'50px' if vertical else '46px'}/1.2 "Songti SC",serif; color:var(--accent); }}
    .calc-step {{ width:90%; display:flex; gap:20px; align-items:center; padding:18px 24px; background:var(--paper); border-radius:18px; font-size:26px; }}
    .pill-row {{ display:flex; flex-wrap:wrap; gap:18px; justify-content:center; }} .pill-row span {{ padding:16px 24px; border-radius:999px; background:var(--paper); border:2px solid var(--steel); font-size:25px; }}
    .network-visual,.earthwork-visual {{ width:100%; height:100%; min-height:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:18px; }}
    .network-visual svg {{ width:100%; height:78%; overflow:visible; }}
    .network-activity {{ fill:none; stroke:var(--steel); stroke-width:7; stroke-linecap:round; }}
    .critical-activity {{ stroke:var(--steel); }}
    .network-arrow {{ fill:var(--steel); stroke:none; }}
    .network-node circle {{ fill:var(--paper); stroke:var(--ink); stroke-width:6; }}
    .network-node text {{ fill:var(--ink); font-size:30px; font-weight:800; }}
    .network-node .node-time {{ fill:var(--steel); font-size:18px; font-weight:600; }}
    .network-label rect {{ fill:var(--paper); stroke:rgba(82,101,119,.32); stroke-width:2; }}
    .network-label text {{ fill:var(--ink); font-size:18px; font-weight:700; }}
    .metric-row {{ display:flex; flex-wrap:wrap; gap:14px; justify-content:center; }}
    .metric-chip {{ padding:11px 18px; border-radius:999px; background:var(--paper); border:2px solid var(--steel); color:var(--ink); font-size:{'21px' if vertical else '19px'}; font-weight:700; }}
    .earthwork-visual svg {{ width:100%; height:66%; overflow:visible; }}
    .earth-cut {{ fill:rgba(233,121,50,.18); transform-box:fill-box; transform-origin:center top; }}
    .earth-outline,.earth-surface,.dimension {{ fill:none; stroke:var(--ink); stroke-width:6; stroke-linecap:round; stroke-linejoin:round; }}
    .dimension {{ stroke:var(--accent); stroke-width:4; }}
    .dimension-label,.slope-label,.earth-plan text {{ fill:var(--ink); font-size:22px; font-weight:700; }}
    .slope-label {{ fill:var(--accent); }}
    .earth-plan rect {{ fill:rgba(252,250,245,.9); stroke:var(--steel); stroke-width:4; transform-box:fill-box; transform-origin:center; }}
    .earth-plan .plan-mid {{ fill:rgba(82,101,119,.10); }} .earth-plan .plan-bottom {{ fill:rgba(233,121,50,.20); stroke:var(--accent); }}
    .formula-stages {{ width:100%; display:grid; grid-template-columns:{'1fr 1fr' if vertical else 'repeat(4,1fr)'}; gap:12px; }}
    .formula-stage {{ min-height:68px; display:flex; align-items:center; gap:12px; padding:12px 14px; border-radius:15px; background:var(--paper); border:2px solid rgba(82,101,119,.25); font-size:{'20px' if vertical else '17px'}; line-height:1.35; }}
    .formula-stage span {{ flex:none; width:34px; height:34px; border-radius:50%; display:grid; place-items:center; background:var(--accent); color:white; font-weight:800; }}
    .cashflow-visual,.component-volume-visual,.flow-schedule-visual {{ width:100%; height:100%; min-height:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:14px; }}
    .cashflow-visual svg,.component-volume-visual svg,.flow-schedule-visual svg {{ width:100%; height:{'65%' if vertical else '68%'}; overflow:visible; }}
    .cash-axis {{ stroke:var(--ink); stroke-width:6; }}
    .cash-arrow {{ stroke-width:10; stroke-linecap:round; transform-box:fill-box; transform-origin:center bottom; }}
    .cash-arrow.positive {{ stroke:var(--accent); }} .cash-arrow.negative {{ stroke:var(--danger); }}
    .cash-head.positive {{ fill:var(--accent); }} .cash-head.negative {{ fill:var(--danger); }}
    .cash-label {{ fill:var(--ink); font-size:24px; font-weight:800; }} .cash-period,.cash-rate {{ fill:var(--steel); font-size:21px; font-weight:700; }}
    .discount-row {{ width:100%; display:flex; flex-wrap:wrap; gap:10px; justify-content:center; }}
    .discount-chip {{ padding:10px 14px; border:2px solid rgba(82,101,119,.28); border-radius:999px; background:var(--paper); font-size:{'18px' if vertical else '16px'}; }}
    .cash-result,.volume-total,.flow-result {{ color:var(--accent); font:800 {'46px' if vertical else '38px'}/1.1 "Songti SC",serif; }}
    .volume-block {{ transform-box:fill-box; transform-origin:center; }}
    .volume-block rect,.volume-block polygon {{ stroke:var(--ink); stroke-width:4; }}
    .volume-block.column rect,.volume-block.column polygon {{ fill:rgba(233,121,50,.23); }}
    .volume-block.beam rect,.volume-block.beam polygon {{ fill:rgba(82,101,119,.17); }}
    .volume-block.slab rect,.volume-block.slab polygon {{ fill:rgba(185,84,27,.14); }}
    .volume-block text {{ fill:var(--ink); font-size:27px; font-weight:800; }}
    .volume-chips {{ width:100%; display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
    .volume-chip {{ display:grid; grid-template-columns:auto 1fr; gap:5px 10px; padding:12px; border-radius:14px; background:var(--paper); border:2px solid rgba(82,101,119,.24); font-size:{'18px' if vertical else '16px'}; }}
    .volume-chip b {{ color:var(--accent); font-size:22px; }} .volume-chip span {{ align-self:center; }} .volume-chip strong {{ grid-column:1/-1; color:var(--ink); }}
    .flow-grid {{ stroke:rgba(82,101,119,.35); stroke-width:3; }}
    .flow-block {{ transform-box:fill-box; transform-origin:left center; }}
    .flow-block rect {{ stroke:var(--ink); stroke-width:3; }} .flow-block.process-0 rect {{ fill:rgba(233,121,50,.30); }} .flow-block.process-1 rect {{ fill:rgba(82,101,119,.20); }} .flow-block.process-2 rect {{ fill:rgba(185,84,27,.18); }}
    .flow-block text,.flow-process,.flow-time {{ fill:var(--ink); font-size:21px; font-weight:800; }} .flow-time {{ fill:var(--steel); }}
    .flow-metrics {{ display:flex; flex-wrap:wrap; justify-content:center; gap:12px; }} .flow-metrics span {{ padding:10px 15px; border-radius:999px; border:2px solid var(--steel); background:var(--paper); font-size:{'19px' if vertical else '17px'}; }}
    .project-label {{ position:absolute; z-index:5; top:{'118px' if vertical else '92px'}; left:{'56px' if vertical else '84px'}; color:var(--steel); font-size:{'20px' if vertical else '18px'}; }}
  </style>
</head>
<body>
  <div id="root" data-composition-id="main" data-width="{width}" data-height="{height}" data-start="0" data-duration="{timeline['total']}">
    <div class="project-label" data-layout-allow-overlap>{e(project_label)}</div>
    {scenes}
    <div id="subtitle-layer"></div>
    {' '.join(audio_tags)}
  </div>
  <script>
    window.__timelines = window.__timelines || {{}};
    const tl = gsap.timeline({{paused:true}});
    const WIDTH = {width};
    const HEIGHT = {height};
    const SEGMENTS = {timeline_js};
    const subLayer = document.getElementById("subtitle-layer");
    SEGMENTS.forEach((seg, index) => {{
      const n = index + 1, t = seg.start;
      const scene = document.getElementById("s" + n);
      const sectionTag = scene.querySelector(".section-tag");
      const visualPanel = scene.querySelector(".visual-panel");
      const knowledgeCard = scene.querySelector(".knowledge-card");
      const sourceLabel = scene.querySelector(".source-label");
      const sub = document.createElement("div");
      sub.className = "subtitle"; sub.id = `sub-${{n}}`; sub.textContent = seg.subtitle; subLayer.appendChild(sub);
      tl.fromTo(sectionTag, {{x:30,opacity:0}}, {{x:0,opacity:1,duration:.45,ease:"power2.out"}}, t+.18);
      tl.fromTo(visualPanel, {{y:34,opacity:0}}, {{y:0,opacity:1,duration:.7,ease:"power3.out"}}, t+.32);
      tl.fromTo(knowledgeCard, {{x:{'-46' if vertical else '58'},opacity:0}}, {{x:0,opacity:1,duration:.65,ease:"back.out(1.18)"}}, t+.68);
      tl.set(sourceLabel, {{visibility:"hidden"}}, t);
      tl.set(sourceLabel, {{visibility:"visible"}}, t+1.05);
      tl.fromTo(sourceLabel, {{y:6}}, {{y:0,duration:.35,ease:"sine.out"}}, t+1.05);
      scene.querySelectorAll(".draw").forEach((path,pathIndex) => {{
        const length = Math.ceil(path.getTotalLength()); path.style.strokeDasharray=length;
        tl.fromTo(path, {{strokeDashoffset:length}}, {{strokeDashoffset:0,duration:.9,ease:"power2.inOut"}}, t+.4+pathIndex*.08);
      }});
      scene.querySelectorAll(".step,.calc-step,.comparison section,.pill-row span").forEach((item,itemIndex) => {{
        tl.set(item, {{visibility:"hidden"}}, t);
        tl.set(item, {{visibility:"visible"}}, t+.85+itemIndex*.16);
        tl.fromTo(item, {{y:22}}, {{y:0,duration:.38,ease:"power2.out"}}, t+.85+itemIndex*.16);
      }});
      scene.querySelectorAll(".network-node").forEach((node,nodeIndex) => {{
        tl.fromTo(node, {{scale:.35,opacity:0,transformOrigin:"50% 50%",transformBox:"fill-box"}}, {{scale:1,opacity:1,duration:.36,ease:"back.out(1.5)"}}, t+.48+nodeIndex*.13);
      }});
      scene.querySelectorAll(".network-label").forEach((label,labelIndex) => {{
        tl.fromTo(label, {{y:10,opacity:0}}, {{y:0,opacity:1,duration:.28,ease:"power2.out"}}, t+1.1+labelIndex*.11);
      }});
      scene.querySelectorAll(".metric-chip").forEach((chip,chipIndex) => {{
        tl.fromTo(chip, {{scale:.85,opacity:0}}, {{scale:1,opacity:1,duration:.3,ease:"back.out(1.4)"}}, t+1.85+chipIndex*.18);
      }});
      scene.querySelectorAll("path.critical-activity").forEach((edge,edgeIndex) => {{
        tl.to(edge, {{stroke:"#B9541B",strokeWidth:11,duration:.42,ease:"power2.out"}}, t+2.35+edgeIndex*.16);
      }});
      scene.querySelectorAll(".network-arrow.critical-activity").forEach((arrow,arrowIndex) => {{
        tl.to(arrow, {{fill:"#B9541B",duration:.42,ease:"power2.out"}}, t+2.35+arrowIndex*.16);
      }});
      const earthCut = scene.querySelector(".earth-cut");
      if (earthCut) tl.fromTo(earthCut, {{scaleY:0,opacity:0}}, {{scaleY:1,opacity:1,duration:.9,ease:"power3.out"}}, t+.55);
      scene.querySelectorAll(".dimension-label,.slope-label").forEach((label,labelIndex) => {{
        tl.fromTo(label, {{opacity:0}}, {{opacity:1,duration:.3,ease:"sine.out"}}, t+1.1+labelIndex*.18);
      }});
      scene.querySelectorAll(".earth-plan rect").forEach((shape,shapeIndex) => {{
        tl.fromTo(shape, {{scale:.62,opacity:0}}, {{scale:1,opacity:1,duration:.5,ease:"back.out(1.25)"}}, t+1.05+shapeIndex*.22);
      }});
      scene.querySelectorAll(".earth-plan text").forEach((label,labelIndex) => {{
        tl.fromTo(label, {{y:8,opacity:0}}, {{y:0,opacity:1,duration:.28,ease:"power2.out"}}, t+1.45+labelIndex*.12);
      }});
      scene.querySelectorAll(".formula-stage").forEach((stage,stageIndex) => {{
        tl.set(stage, {{visibility:"hidden"}}, t);
        tl.set(stage, {{visibility:"visible"}}, t+2.0+stageIndex*.22);
        tl.fromTo(stage, {{x:18,scale:.94}}, {{x:0,scale:1,duration:.34,ease:"power2.out"}}, t+2.0+stageIndex*.22);
      }});
      scene.querySelectorAll(".cash-arrow").forEach((arrow,arrowIndex) => {{
        tl.fromTo(arrow, {{scaleY:0}}, {{scaleY:1,duration:.46,ease:"back.out(1.25)"}}, t+.75+arrowIndex*.18);
      }});
      scene.querySelectorAll(".cash-head,.cash-label,.cash-period,.discount-chip").forEach((item,itemIndex) => {{
        tl.set(item, {{visibility:"hidden"}}, t);
        tl.set(item, {{visibility:"visible"}}, t+1.2+itemIndex*.08);
        tl.fromTo(item, {{scale:.72,transformOrigin:"50% 50%",transformBox:"fill-box"}}, {{scale:1,duration:.3,ease:"back.out(1.3)"}}, t+1.2+itemIndex*.08);
      }});
      const cashResult = scene.querySelector(".cash-result");
      if (cashResult) {{
        tl.set(cashResult, {{visibility:"hidden"}}, t);
        tl.set(cashResult, {{visibility:"visible"}}, t+2.7);
        tl.fromTo(cashResult, {{scale:.78}}, {{scale:1,duration:.38,ease:"back.out(1.4)"}}, t+2.7);
      }}
      scene.querySelectorAll(".volume-block").forEach((block,blockIndex) => {{
        const offsets = [-95,0,95];
        tl.fromTo(block, {{x:-offsets[blockIndex],scale:.58,rotation:-4+blockIndex*4}}, {{x:0,scale:1,rotation:0,duration:.72,ease:"back.out(1.25)"}}, t+.65+blockIndex*.26);
      }});
      scene.querySelectorAll(".volume-chip").forEach((chip,chipIndex) => {{
        tl.fromTo(chip, {{y:18,opacity:0}}, {{y:0,opacity:1,duration:.32,ease:"power2.out"}}, t+1.65+chipIndex*.2);
      }});
      const volumeTotal = scene.querySelector(".volume-total");
      if (volumeTotal) tl.fromTo(volumeTotal, {{scale:.8,opacity:0}}, {{scale:1,opacity:1,duration:.4,ease:"back.out(1.4)"}}, t+2.55);
      scene.querySelectorAll(".flow-block").forEach((block,blockIndex) => {{
        tl.fromTo(block, {{scaleX:0}}, {{scaleX:1,duration:.34,ease:"power2.out"}}, t+.75+blockIndex*.11);
      }});
      scene.querySelectorAll(".flow-time,.flow-process,.flow-metrics span").forEach((item,itemIndex) => {{
        tl.fromTo(item, {{y:8,opacity:0}}, {{y:0,opacity:1,duration:.26,ease:"power2.out"}}, t+1.1+itemIndex*.07);
      }});
      const flowResult = scene.querySelector(".flow-result");
      if (flowResult) tl.fromTo(flowResult, {{scale:.8,opacity:0}}, {{scale:1,opacity:1,duration:.38,ease:"back.out(1.4)"}}, t+2.7);
      tl.fromTo(sub, {{y:16,opacity:0}}, {{y:0,opacity:1,duration:.3,ease:"power2.out"}}, t+.65);
      tl.to(sub, {{opacity:0,duration:.22,ease:"power1.in"}}, t+seg.duration-.25);
      tl.set(sub, {{visibility:"hidden"}}, t+seg.duration);
    }});
    for (let i=1;i<SEGMENTS.length;i++) {{
      const prev=SEGMENTS[i-1], cur=SEGMENTS[i], t=cur.start;
      tl.set(cur.sel, {{display:"block",opacity:1}}, t);
      if (prev.transition === "push-up") {{
        tl.to(prev.sel, {{y:-HEIGHT,opacity:1,duration:.5,ease:"power3.inOut"}}, t);
        tl.fromTo(cur.sel, {{y:HEIGHT,opacity:1}}, {{y:0,opacity:1,duration:.5,ease:"power3.inOut"}}, t);
      }} else {{
        tl.to(prev.sel, {{x:-WIDTH,opacity:1,duration:.5,ease:"power3.inOut"}}, t);
        tl.fromTo(cur.sel, {{x:WIDTH,opacity:1}}, {{x:0,opacity:1,duration:.5,ease:"power3.inOut"}}, t);
      }}
      tl.set(prev.sel, {{display:"none"}}, t+.55);
    }}
    window.__timelines["main"] = tl;
  </script>
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
        output.write_text(build_html(project, storyboard, timeline, profile, include_audio), encoding="utf-8")
        print(f"Generated {profile}: {output}")
    if timeline.get("preview_timing"):
        print("WARN: audio/durations.json is missing; compositions use estimated preview timing")
    if not include_audio:
        print("WARN: one or more audio segments are missing; generated compositions are silent previews")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
