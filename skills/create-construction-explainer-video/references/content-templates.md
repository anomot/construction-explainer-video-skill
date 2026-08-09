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

推荐 `visual_type`: `calculation`、`network-plan`、`earthwork-volume`、`cashflow`、`component-volume`、`flow-schedule`；将公式放 `formula`，步骤放 `steps`，关键结果放 `key_number`。

### 动态图形计算

- `network-plan`：用于双代号网络图、节点时间、总时差和关键线路。把节点坐标放入 `network.nodes`，把工作逻辑、持续时间和关键状态放入 `network.activities`，结论摘要放入 `network.metrics`。
- `earthwork-volume`：用于放坡几何、顶底尺寸、三截面和体积代入。把底长、底宽、深度和演示放坡值放入 `geometry`。正式内容不得把演示假定直接当作清单、定额或施工安全规则。
- `cashflow`：用于现金流量图、逐期折现和净现值；输入 `cashflow.flows` 与 `cashflow.rate`。
- `component-volume`：用于独立构件的几何拆分与汇总；输入 `component_volume.components`。
- `flow-schedule`：用于等节奏流水横道与工期；输入 `flow_schedule.sections`、`processes` 和 `rhythm`。
- 动画顺序必须与旁白一致：先画主几何，再出现尺寸/时间参数，再代入公式，最后高亮结果。
- 每个数值例题保存独立计算底稿；数字、单位、路径和公式必须能够手工复算。

## 旁白规范

- 每段通常 25–70 个中文字符，使用短句和自然停顿。
- 数字、单位、规范号和多音字按希望的读法写入 TTS 文本或发音词典。
- 公式不逐符号朗读：画面写公式，旁白解释变量关系和代入逻辑。
- 避免“必过、押中、百分百”等承诺。
- 末段明确“按指定年度/地区/版本口径，发布前经专业审核”。
