# 输入与项目契约

## 最小输入

满足一项即可：

- 至少一份相关资料；或
- 一个可识别的考试考点、概念或具体描述。

## 默认值

| 字段 | 默认值 |
|---|---|
| 受众 | 备考入门用户 |
| 年度 | 执行当年；影响结论时必须核实 |
| 地区 | 全国；二建地方口径必须明确省市 |
| 时长 | `auto`，目标 90 秒，通常 60–120 秒 |
| 画幅 | `vertical` 1080×1920 与 `landscape` 1920×1080 |
| 配音 | MiniMax 官方 `speech-2.8-hd`，教学型女声 |
| 品牌 | “建知课”工作名，工程纸暖灰＋深蓝灰＋工程橙 |
| 音乐 | 无 |
| 审核 | 人工专业终审 |

## 项目目录

```text
project/
├── project.json
├── inputs/rights.json
├── research/sources.json
├── research/evidence.json
├── research/conflicts.md
├── content/storyboard.json
├── audio/durations.json
├── composition/vertical/index.html
├── composition/landscape/index.html
├── renders/
├── preview/
├── reports/
└── review/review.json
```

## `evidence.json`

```json
{
  "claims": [
    {
      "id": "C01",
      "text": "可上镜的原子结论",
      "risk": "high",
      "source_ids": ["S01"],
      "verified": true,
      "notes": "适用范围、例外或计算过程"
    }
  ]
}
```

## `storyboard.json`

```json
{
  "topic": "后浇带施工要求",
  "voice": {
    "provider": "minimax-official",
    "model": "speech-2.8-hd",
    "voice_id": "female-chengshu",
    "speed": 1.0
  },
  "segments": [
    {
      "id": 1,
      "title": "为什么要留后浇带",
      "narration": "口语化旁白",
      "claim_ids": ["C01"],
      "visual_type": "concept",
      "headline": "屏幕主标题",
      "bullets": ["短要点一", "短要点二"],
      "steps": [],
      "key_number": "",
      "source_label": "来源短名称",
      "transition": "blur-crossfade",
      "min_duration": 6
    }
  ]
}
```

场景数为 5–9。`id` 从 1 连续递增；`claim_ids` 必须存在于证据包。复杂技术图示可以在组合生成后继续编辑 SVG。

## 动态计算扩展字段

`network-plan` 示例：

```json
{
  "visual_type": "network-plan",
  "network": {
    "nodes": [{"id": 1, "x": 90, "y": 280, "early": 0, "late": 0}],
    "activities": [{"from": 1, "to": 2, "label": "A", "duration": 3, "critical": true}],
    "metrics": ["关键线路 1→2→4→6", "总工期 11天"]
  }
}
```

`earthwork-volume` 示例：

```json
{
  "visual_type": "earthwork-volume",
  "geometry": {
    "bottom_length": 12,
    "bottom_width": 8,
    "depth": 3,
    "slope": 0.5
  },
  "steps": ["单侧增加1.5米", "顶口15×11米", "三截面面积", "体积387立方米"]
}
```

坐标采用 SVG `viewBox="0 0 900 560"` 的用户坐标。`slope` 是几何输入；若来自规范、方案或计量规则，必须有独立证据，不得沿用演示默认值。
