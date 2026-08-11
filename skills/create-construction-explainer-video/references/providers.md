# Provider 路由

所有脚本自动从当前目录逐级向上查找 `.env.local` / `.env`（找不到时再回退到 Skill 仓库根），已导出的环境变量始终优先；也可用 `--env-file` 显式指定。

## MiniMax 官方 TTS

- Endpoint：`POST https://api.minimaxi.com/v1/t2a_v2`
- 环境变量：`MINIMAX_API_KEY`；可选 `MINIMAX_API_HOST`、`MINIMAX_TTS_VOICE_ID`（默认音色）。
- 模型：`speech-2.8-hd`
- 默认：32 kHz、128 kbps、MP3、单声道、非流式。
- 正式女声在首个样片试听后固定；流程默认值为 `female-chengshu`。
- 多音色测试先执行 `python3 scripts/minimax_tts.py --list-voices`（Get Voice API）查询当前账号可用音色；不要凭记忆猜 `voice_id`。已验证的普通话女声包括新闻女声、温暖闺蜜、阅历姐姐、温柔学姐和甜美女声。
- 批量生成按项目串行执行，避免并发请求触发账号 RPM 限制。
- 响应 HTTP 200 不代表成功，必须检查 `base_resp.status_code == 0` 和 `data.audio`。
- 鉴权、参数、余额错误不重试；网络、限流和服务端错误有限重试。

## Qwen Image（第 1 档）

- Endpoint：`POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`
- 环境变量：`DASHSCOPE_API_KEY`
- 模型：`qwen-image-3.0-pro`
- 当前账号已实测公共 Endpoint 可直接调用，不要求 Workspace ID。
- 使用无文字提示词；保存提示词、请求 ID、尺寸、产物哈希和用途。

## Agent 内置图像生成 / OpenAI GPT-Image（第 2 档）

- 当前 agent 环境自带图像生成工具（如 Codex `imagegen`）时直接调用，不假设工具名称，不要求外部凭据。
- 没有内置工具时执行 `scripts/gpt_image.py`：`POST https://api.openai.com/v1/images/generations`，模型 `gpt-image-1`，环境变量 `OPENAI_API_KEY`；接口与 `qwen_image.py` 对齐，产出同样写入 sidecar 元数据。未配置 key 时报错跳到第 3 档。
- 仍受”非关键视觉”边界约束。

## 降级

- TTS 失败：可用 macOS `say` 生成流程预览，但不能标为正式配音。
- 生图三档依次降级：Qwen → 内置工具/GPT-Image → 纯 HTML/SVG，不阻断核心视频。
- ffmpeg/HyperFrames 缺失：交付证据、脚本、分镜和组合源码，明确环境缺口。
