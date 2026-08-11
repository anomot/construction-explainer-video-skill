# 教学结构与分镜模板

## 通用原则

- 使用 5–9 个场景，每场一个核心关系。
- 时长按内容决定，不靠提高语速压缩知识。
- 旁白先讲关系再讲术语；屏幕文字用短语、数字和结构图。
- 每段旁白绑定 `claim_ids`；没有证据的句子删掉或标为待核实。

## 概念解释型

钩子 → 定义 → 构成/机制 → 适用条件 → 易错点 → 总结。

## 法规条款型

情境 → 主体与规则 → 条件 → 例外 → 时间线/责任 → 高频陷阱 → 适用日期与来源。

## 施工流程型

现场错误钩子 → 目的 → 前置条件 → 分步施工 → 质量控制 → 验收/养护 → 高频错误总结。

推荐 `visual_type`: `concept`、`process`、`comparison`、`timeline`、`summary`。

## 计算例题型

题干条件 → 识别对象 → 公式与单位 → 分步代入 → 结果复算 → 易错点 → 得分点总结。

推荐 `visual_type`: `calculation`、`network-plan`、`earthwork-volume`、`cashflow`、`component-volume`、`flow-schedule`、`rebar-length`、`earned-value`；将公式放 `formula`，步骤放 `steps`，关键结果放 `key_number`。

### 动态图形计算

- `network-plan`：用于双代号网络图、节点时间、总时差和关键线路。把节点坐标放入 `network.nodes`，把工作逻辑、持续时间和关键状态放入 `network.activities`，结论摘要放入 `network.metrics`。
- `earthwork-volume`：用于放坡几何、顶底尺寸、三截面和体积代入。把底长、底宽、深度和演示放坡值放入 `geometry`。正式内容不得把演示假定直接当作清单、定额或施工安全规则。
- `cashflow`：用于现金流量图、逐期折现和净现值；输入 `cashflow.flows` 与 `cashflow.rate`。
- `component-volume`：用于独立构件的几何拆分与汇总；输入 `component_volume.components`。
- `flow-schedule`：用于等节奏流水横道与工期；输入 `flow_schedule.sections`、`processes` 和 `rhythm`。
- `rebar-length`：用于钢筋下料长度与弯折段；输入 `rebar.segments`（分段长度与转向），分段累加条自动生成。
- `earned-value`：用于挣值法三曲线与 CV/SV；输入 `earned_value.periods/pv/ev/ac` 与 `focus_period`。
- 动画顺序必须与旁白一致：先画主几何，再出现尺寸/时间参数，再代入公式，最后高亮结果。
- 每个数值例题保存独立计算底稿；数字、单位、路径和公式必须能够手工复算。

### 旁白与动画节拍对位

动画节拍会把各动画组均匀铺满整段旁白窗口，因此**写旁白时按动画组顺序组织语句**。各 visual_type 的组序：

| visual_type | 动画组顺序（旁白按此顺序讲） |
|---|---|
| network-plan | net-nodes → net-edges → net-labels → net-times（早）→ net-late（迟）→ net-critical → net-metrics |
| earthwork-volume | earth-section(+cut) → earth-dims → earth-plans → earth-steps |
| cashflow | cash-axis → cash-arrows → cash-rate → cash-discounts → cash-result |
| component-volume | vol-base → vol-blocks → vol-chips → vol-total |
| flow-schedule | flow-grid → flow-blocks → flow-metrics → flow-result |
| rebar-length | rebar-path(+bends) → rebar-dims → rebar-bars → rebar-result |
| projection-point | proj-planes(+labels) → proj-point → proj-arrows → proj-rays → proj-feet → proj-result（system 场景无 arrows；unfold 场景无 point；缺席组写入 static_groups 以收紧节拍） |
| earned-value | ev-axes → ev-pv → ev-ev → ev-ac → ev-gaps → ev-chips |
| calculation | calc-formula → calc-steps → calc-result |
| process/timeline | step-items 依次 |

多步演示（同一图形连续讲多场）从第二场起用 `animation.mode: "continue"`，只讲并动画新增的组；旁白开头不要再重复描述整图。需要让某组恰好落在某句旁白上时，用 `animation.beats` 指定该组的 `at` 分数（该句起点时间 ÷ 场景总时长）。

## 旁白规范

- 每段通常 25–70 个中文字符，使用短句和自然停顿。
- 数字、单位、规范号和多音字按希望的读法写入 TTS 文本或发音词典。
- 公式不逐符号朗读：画面写公式，旁白解释变量关系和代入逻辑。
- 避免“必过、押中、百分百”等承诺。
- 末段明确“按指定年度/地区/版本口径，发布前经专业审核”。
