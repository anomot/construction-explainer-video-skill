---
name: create-construction-explainer-video
description: 将一级建造师、二级建造师、一级造价工程师的考点、教材、讲义、题目或具体工程知识描述，制作成有来源证据、中文配音、同步字幕、确定性技术图示、9:16 与 16:9 双画幅的建筑知识讲解视频。用户只有一个概念而没有资料时也使用本 Skill，先检索权威来源再制作。适用于视频号、抖音、小红书、B 站和课程平台，以及脚本、分镜、封面、审阅版、局部重做和人工专业终审工作流；不用于注册建筑师首版内容、施工图设计或无人审核的工程决策。
---

# 建筑考证讲解视频

把建筑考证知识转化为可追溯、可审阅、可复现的横竖双版教学视频。先验证事实，再写教学内容；所有技术文字、尺寸、公式、节点和工序关系均确定性渲染。

## 核心门禁

1. 只启用 `constructor-level-1`、`constructor-level-2`、`cost-engineer-level-1`。把“建筑工程师”等歧义输入先归一化；注册建筑师转为超出 MVP 范围。
2. 没有资料时必须联网检索；关键结论来源覆盖率未达 100% 时只交付研究缺口，不生成正式版。
3. 教材、讲义和题库只作为内部研究材料，除非有公开复用授权。禁止整页、大段或系统性复刻。
4. 生成图只承载情境和气氛，不承载技术结论。技术内容使用 HTML/SVG/CSS/GSAP。
5. 自动检查通过只能生成“审阅版”。没有人工专业终审批准记录时不得命名或描述为正式发布版。

## 统一工作流

### 1. 受理与建项

读取 `references/input-schema.md`。资料或明确主题二者有一即可启动；默认受众为备考入门用户，时长按内容自适应，目标 90 秒，输出 9:16 与 16:9。

新项目先执行：

```bash
python3 scripts/init_project.py <project-dir> \
  --exam-track constructor-level-1 \
  --subject "建筑工程管理与实务" \
  --topic "后浇带施工要求"
```

不要重复询问默认项。只确认会改变结论的考试类别、年度、地区、来源冲突、资料权利或敏感信息。

### 2. 建立证据包

读取 `references/source-policy.md` 和与考试类别对应的 `references/exam-tracks.md` 段落。

- 有资料：提取页码、表格、图注、发布日期、权利状态；再用现行官方来源核对时效。
- 无资料：按官方法规/主管部门/考试机构/现行标准优先级检索，保存检索截止日期。
- 将来源写入 `research/sources.json`，将每条可上镜结论写入 `research/evidence.json`。
- 对冲突、废止状态和无法确认的条款写入 `research/conflicts.md`，不要静默择一。

在写脚本前执行：

```bash
python3 scripts/validate_project.py <project-dir> --stage research
```

### 3. 写教学脚本与分镜

读取 `references/content-templates.md`，按主题选择概念、法规、施工流程或计算模板。涉及图形计算时再读取 `references/dynamic-calculation-cases.md`，优先使用可复算的动态组件。把结果写入 `content/storyboard.json`：

- 使用 5–9 个场景；每场只讲一个判断或关系。
- 每段旁白使用短句，数字和单位写成正确读法；不要让 TTS 逐符号读公式。
- 每段填写 `claim_ids`，必须映射到证据包。
- 屏幕文字使用 `headline`、`bullets`、`key_number`、`steps` 等结构化字段，不把整段旁白堆到画面。
- 首段给考试/现场钩子，末段总结高频错误、适用口径和来源截止日期。

写完执行：

```bash
python3 scripts/validate_project.py <project-dir> --stage content
```

### 4. 制作视觉

读取 `references/visual-system.md`。主视觉使用工程纸暖灰、深蓝灰和工程橙；双画幅共享内容模型但独立排版，禁止裁切互转。

非关键插图按顺序路由：

1. 百炼 `qwen-image-3.0-pro`：执行 `scripts/qwen_image.py`。
2. Codex 内置 `imagegen`：直接调用图像生成工具，不要求外部凭据。
3. 失败时回退到纯 SVG/HTML，不阻断视频。

任何生成图都要目视复核。发现伪文字、错误节点、钢筋或尺寸时删除错误信息，不以生成图为技术依据。

### 5. 生成配音与时间轴

正式 TTS 使用 MiniMax 官方 API：`https://api.minimaxi.com/v1/t2a_v2`，模型 `speech-2.8-hd`，凭据只读 `MINIMAX_API_KEY`。

```bash
python3 scripts/minimax_tts.py <project-dir>/content/storyboard.json \
  --outdir <project-dir>/audio
```

默认女声先用 `female-chengshu`；首个样片前生成 2–3 个女声音色试听并固定项目音色。重写旁白或换音色后必须重跑 TTS；`audio/durations.json` 是场景时间轴唯一真源。

### 6. 生成双画幅组合并渲染

```bash
python3 scripts/build_compositions.py <project-dir>
bash scripts/build_video.sh <project-dir> --draft
```

组合生成到 `composition/vertical/` 与 `composition/landscape/`。`network-plan`、`earthwork-volume`、`cashflow`、`component-volume` 与 `flow-schedule` 已提供确定性动态基线；其他技术节点、构造剖面和复杂计算必须进一步编辑 SVG，再运行 HyperFrames `check` 和渲染。

### 7. 联合质检与人工终审

读取 `references/quality-gates.md`。

```bash
python3 scripts/verify_output.py <project-dir>
python3 scripts/validate_project.py <project-dir> --stage publish
```

逐场景检查来源、术语、数字、单位、公式、字幕、发音、遮挡、箭头和画幅安全区。先生成 `review` 文件名；只有 `review/review.json` 的状态为 `approved` 且记录审核人、时间和版本后，才允许标记正式版。

## 局部重做

- 改来源或结论：使关联 `claim_ids`、脚本和场景失效，重新执行 research/content 门禁。
- 改旁白或音色：只重做受影响音频、时间轴、字幕和组合。
- 改视觉：保留证据和音频，只重做对应 SVG/HTML 与横竖布局。
- 改画幅：共享脚本与音频，重新生成该画幅组合，不裁切另一画幅。

## 资源导航

- `references/input-schema.md`：输入、项目目录与 JSON 契约。
- `references/source-policy.md`：来源、时效、版权和敏感资料规则。
- `references/exam-tracks.md`：一建、二建、一造分类与风险点。
- `references/content-templates.md`：四类教学结构与分镜字段。
- `references/dynamic-calculation-cases.md`：图形计算测试用例、动态行为与风险边界。
- `references/visual-system.md`：品牌、双画幅和确定性技术图示规则。
- `references/providers.md`：MiniMax、Qwen Image、内置 imagegen 与降级策略。
- `references/quality-gates.md`：自动检查、人工终审和发布门禁。
