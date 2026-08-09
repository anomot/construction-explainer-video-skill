# Provider 路由

## MiniMax 官方 TTS

- Endpoint：`POST https://api.minimaxi.com/v1/t2a_v2`
- 环境变量：`MINIMAX_API_KEY`
- 模型：`speech-2.8-hd`
- 默认：32 kHz、128 kbps、MP3、单声道、非流式。
- 正式女声在首个样片试听后固定；流程默认值为 `female-chengshu`。
- 多音色测试必须先通过 Get Voice API 查询当前账号可用音色；不要凭记忆猜 `voice_id`。当前已验证的普通话女声包括新闻女声、温暖闺蜜、阅历姐姐、温柔学姐和甜美女声。
- 批量生成按项目串行执行，避免并发请求触发账号 RPM 限制。
- 响应 HTTP 200 不代表成功，必须检查 `base_resp.status_code == 0` 和 `data.audio`。
- 鉴权、参数、余额错误不重试；网络、限流和服务端错误有限重试。

## Qwen Image

- Endpoint：`POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`
- 环境变量：`DASHSCOPE_API_KEY`
- 模型：`qwen-image-3.0-pro`
- 当前账号已实测公共 Endpoint 可直接调用，不要求 Workspace ID。
- 使用无文字提示词；保存提示词、请求 ID、尺寸、产物哈希和用途。

## Codex 内置 imagegen

- 作为 Qwen 的视觉方案对照或失败备用。
- 直接调用内置图像生成工具，不在脚本中假设 Provider Endpoint 或额外 API Key。
- 仍受“非关键视觉”边界约束。

## 降级

- TTS 失败：可用 macOS `say` 生成流程预览，但不能标为正式配音。
- Qwen/imagegen 失败：改用纯 HTML/SVG，不阻断核心视频。
- ffmpeg/HyperFrames 缺失：交付证据、脚本、分镜和组合源码，明确环境缺口。
