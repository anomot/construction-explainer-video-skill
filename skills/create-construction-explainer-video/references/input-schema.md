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

`transition` 表示"进入下一场"的方式，可选：`blur-crossfade`（默认，交叉淡化）、`push-up`、`push-left`、`hold`（原位淡入，续演场景自动使用）。

## 动画节拍字段（可选）

每个场景可携带 `animation` 字段，控制动画组在场景时长内的分布：

```json
{
  "animation": {
    "mode": "continue",
    "static_groups": ["net-nodes", "net-edges", "net-heads", "net-labels"],
    "beats": [
      {"group": "net-times", "at": 0.3, "stagger": 0.08},
      {"group": "net-metrics", "at": 0.75}
    ]
  }
}
```

- `mode`: `build`（默认，全部组做入场动画）或 `continue`（续演：`static_groups` 内的组开场即静态就位，只动画其余组）。`continue` 要求上一场景为相同 `visual_type`，且进入转场自动为 `hold`。
- `static_groups`: 省略时按 visual_type 使用默认结构组（网络图为节点/箭线/名称，几何图为剖面/尺寸线等）。
- `beats`: 精调各组锚点。`at` 是场景时长的分数（0–0.95，应递增）；`stagger` 是组内元素间隔（同为时长分数）。未指定的组按默认顺序均匀分布在整段旁白窗口内。
- 各 visual_type 的动画组名清单见 `content-templates.md`。

不写 `animation` 时动画仍会自动铺满场景时长；只有需要与旁白精确对位或续演时才写。

## 字幕切分

旁白按 `。！？；` 切句，超长句再按逗号切分为 ≤34 字的片段；各片段在配音窗口内按字符数比例排布，依次显示。竖版字幕最多两行；不需要人工填写字幕字段。

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

`rebar-length` 示例（`turn` 表示画本段前的转向角度，正值逆时针；`total` 可选，写入时会与分段和校验）：

```json
{
  "visual_type": "rebar-length",
  "rebar": {
    "unit": "mm",
    "segments": [
      {"label": "左锚固", "length": 300},
      {"label": "水平段", "length": 4200, "turn": -90, "bend_label": "90°"},
      {"label": "右锚固", "length": 300, "turn": -90, "bend_label": "90°"}
    ],
    "total": 4800
  }
}
```

`earned-value` 示例（三序列长度必须一致；`focus_period` 是要展开 CV/SV 的期序号）：

```json
{
  "visual_type": "earned-value",
  "earned_value": {
    "unit": "万元",
    "periods": ["1月", "2月", "3月", "4月"],
    "pv": [100, 220, 360, 500],
    "ev": [90, 200, 330, 450],
    "ac": [110, 240, 370, 480],
    "focus_period": 3,
    "metrics": ["CV = EV - AC = -30", "SV = EV - PV = -50"]
  }
}
```

`projection-point` 示例（三面投影体系；`stage` 取 `system`（轴测体系）或 `unfold`（展开成图）；`point` 必须严格位于 `extent` 内部，`extent` 缺省为 40/24/30）：

```json
{
  "visual_type": "projection-point",
  "projection": {
    "stage": "system",
    "point": {"x": 26, "y": 15, "z": 20},
    "point_label": "A",
    "show_projections": false,
    "result_label": "三面投影体系"
  }
}
```

- `show_projections: false` 时省略投影线与三个投影（用于只介绍体系的场景），下一场用 `continue` 补画投影即可无缝续演。
- `unfold` 场景与 `system` 场景几何不同，不要用 `continue` 连接，改用 push 转场。

所有动态类型都必须提供对应数据块；缺失时 `build_compositions.py` 与 `validate_project.py` 都会报错，不会渲染演示数据。
