# 电商文案 Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付可嵌入其他 Python 程序的电商文案 Agent，以及调用同一核心包的最简桌面测试工具。

**Architecture:** 用独立数据模型和 `ModelAdapter` 协议隔离业务与模型服务，以 LangGraph 组织输入校验、生成、检查和一次修正。Tkinter 仅负责收集参数和展示结果；其他 Python 程序直接调用同步或异步接口。

**Tech Stack:** Python 3.11+、LangGraph、Pydantic 2、OpenAI Python SDK、Pillow、Tkinter/ttk；uv 管理环境，pytest、pytest-asyncio 和 httpx MockTransport 用于测试。执行时解析可用的兼容依赖版本并提交 `uv.lock`，不使用未经安装验证的固定版本号。

**Spec:** `docs/superpowers/specs/2026-09-30-ecommerce-copy-agent-design.md`（用户已确认）。

**执行结果：** 首版已由多个 Agent 实现并通过分项与最终独立审查。102 项自动化测试、真实 Tk 交互冒烟、构建与独立环境安装验证通过。无 Git 仓库，提交步骤不适用；真实中转站与人工视觉验收未执行。详见 `docs/verification.md`（相对项目根目录）。

## Global Constraints

- 核心包名称为 `ecommerce_copy_agent`，不导入 Tkinter，不依赖窗口或桌面配置。
- 模型名称、API 地址和密钥可配置；首版内置 `openai_chat`，不默认支持其他协议。生成参数由具体适配器配置持有；工作流只传递图文业务请求，不维护第二套生成参数。
- 默认生成一份文案，默认语言为简体中文；平台和文案类型接受自定义文本。
- 首版每次最多四张图片，每张不超过 10 MiB；接受 JPEG、PNG、WebP 的静态图片，并检查实际内容与类型是否匹配。
- 最大字符数为可选正整数：按去除首尾空白后的文案正文计算 Python 字符串长度，正文中的标点、空格和换行计数。
- `supports_images` 默认关闭，单次模型请求默认超时 60 秒；不静默丢弃图片。
- 单次业务调用最多发起两次模型请求；底层 SDK 的自动重试设为零；服务错误不触发修正。
- 模型必须返回包含 `text` 和 `warnings` 的 JSON 对象；程序填写调用次数、模型和用量元数据。
- 任一次请求缺少 token 用量时，最终 `usage` 为 `None`；完整用量才求和。
- 密钥不写入仓库、日志、结果对象或默认配置文件；失败时不返回模拟文案冒充真实结果。
- 不实现 HTTP 服务、数据库、账号、联网搜索、长期记忆、批量任务或多 Agent 协作。
- 未验证真实中转站或图形界面的行为必须在交付中说明。

## Review Focus

1. 同一个 Agent 连续调用或异步并发调用时，图片、修正次数和警告不能跨请求串用，客户端和 transport 不能因前次关闭而失效；由任务 4 的隔离测试及真实适配器的模拟 HTTP 集成测试覆盖。
2. Windows 中文路径、损坏图片、扩展名与实际格式不符及解压后过大图片应有明确错误；由任务 2 的图片测试覆盖。
3. 中转站返回的错误正文可能回显密钥，超时和认证失败也不能产生 SDK 隐藏重试；由任务 3 的传输测试覆盖。
4. 模型返回空白正文、JSON 字符串而非对象、非字符串警告或缺少 usage 时，应保持结果契约和用量语义；由任务 4 的流程测试覆盖。
5. 生成期间再次点击、关闭窗口，以及前次成功后生成失败，不能导致并行误提交、销毁后写控件或复制旧文案；由任务 5 的 Tkinter 生命周期冒烟检查覆盖。

## 文件布局与运行约定

项目新增 `pyproject.toml`、`uv.lock`、`.gitignore`、`.env.example`、`README.md`、`AGENTS.md` 和 `docs/product-design.md`。`AGENTS.md` 只链接当前项目设计与界面约定，不引入与本任务无关的规则。

核心位于 `src/ecommerce_copy_agent/`：`schemas.py` 管理公共数据类型，`errors.py` 管理公开错误，`images.py` 验证图片，`adapters/base.py` 定义模型接口，`adapters/openai_chat.py` 转换协议，`prompts.py` 构建提示，`validation.py` 检查输出，`workflow.py` 编排流程，`agent.py` 提供公共调用入口，`config.py` 加载显式配置与环境变量，`__init__.py` 导出稳定接口。

桌面工具置于 `desktop/__init__.py`、`desktop/__main__.py`、`desktop/app.py` 和 `desktop/forms.py`；从项目根目录执行 `uv run python -m desktop`。核心安装包不包含这个桌面目录。示例放在 `examples/`，测试放在 `tests/`。

执行开始时检查 uv 和可用的 Python 3.11+；如果只有 WindowsApps 的 Python 占位入口，不据此宣称 Python 已安装。通过 uv 创建项目环境，若下载依赖受限，使用正常权限流程处理，不改用户全局 Python 环境。后续命令均在项目根目录执行。

环境准备还应在所选解释器中执行 `uv run python -c "import tkinter; print(tkinter.TkVersion)"`，再执行 `uv run python -c "import tkinter as tk; root = tk.Tk(); root.withdraw(); root.update_idletasks(); root.destroy()"`。第一条失败应检查解释器是否自带 `_tkinter` 与 Tcl/Tk，不能用 `pip install tkinter` 修复；第二条失败应区分 Tcl/Tk 初始化问题与显示环境不可用。优先选用本机已有且支持 Tk 的解释器，不更改全局 Python；桌面条件不足不阻塞核心实现，但应记录并保留桌面验收项。

若 uv 默认缓存目录不可写，仅为当前进程设置 `UV_CACHE_DIR` 到项目 `.cache/uv` 或授权的临时目录，将 `.cache/` 加入忽略规则；不更改用户全局 uv 配置。当前检查曾因默认缓存权限失败，尚未据此确认可用的 Python/Tk 运行时。

统一使用 `uv run python -m pytest` 执行测试。桌面冒烟入口为 `uv run python -m tests.manual.desktop_smoke`，并为 `tests/` 和 `tests/manual/` 创建 `__init__.py`，确保从项目根目录解析桌面源码，不依赖外部 `PYTHONPATH`。wheel 独立安装检查则有意切换到项目目录之外执行。

当前目录没有 Git 仓库；本文中的提交步骤仅在执行时已有 Git 仓库的情况下运行，否则记录为不适用，不把提交状态当成软件完成条件。

## Task 1: 可安装的公共数据契约

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/ecommerce_copy_agent/__init__.py`, `src/ecommerce_copy_agent/schemas.py`, `src/ecommerce_copy_agent/errors.py`
- Test: `tests/test_schemas.py`

**Interfaces:**
- Produces: Pydantic 模型 `ProductInfo(name: str, category: str = "", brand: str = "", description: str = "", selling_points: list[str] = [], attributes: dict = {})`；属性值严格限制为字符串、有限数字、布尔值或字符串列表，拒绝嵌套对象和隐式类型转换。
- Produces: `CopyRequirements(copy_type: str = "宣传文案", platform: str = "", audience: str = "", tone: str = "自然", language: str = "简体中文", max_chars: int | None = None, extra_instructions: str = "")`。
- Produces: 判别联合 `ImageInput = FileImage | BytesImage`；`FileImage(kind="file", path: Path)`、`BytesImage(kind="bytes", data: bytes, media_type: str)`；字节使用 Pydantic 的 Base64 JSON 序列化及对应反序列化配置。
- Produces: `CopyRequest(product: ProductInfo, images: list[ImageInput] = [], requirements: CopyRequirements = 默认值)`，`TokenUsage(input_tokens: int, output_tokens: int, total_tokens: int)`，`CopyResult(text: str, warnings: list[str], model: str, usage: TokenUsage | None, request_count: int)`。
- Produces: `AgentError(code: str, message: str)` 以及 `InputError`、`ConfigurationError`、`ModelServiceError`、`OutputValidationError` 子类；公开模型服务错误只保留安全描述。

- [x] **Step 1:** 创建最小 `pyproject.toml` 开发环境和测试文件。测试 `test_blank_product_rejected` 断言纯空白名称失败；`test_requirements_defaults` 断言默认语言为 `简体中文`、文案类型为 `宣传文案`；`test_max_chars_is_strict_positive_integer` 断言 `0`、`-1`、`True`、`1.5` 均失败；`test_custom_attributes_and_copy_type` 断言中文自定义字段与文案类型不丢失；`test_image_json_roundtrip` 断言 `BytesImage` JSON 往返后字节相等；`test_request_defaults_are_isolated` 断言两份请求的列表互不影响。
- [x] **Step 2:** 执行 `uv run python -m pytest tests/test_schemas.py -q`，确认因缺少公共模型而失败；环境安装失败不能充当测试失败证据。
- [x] **Step 3:** 实现以上模型和公开错误，使用默认工厂创建容器；添加源码包发现配置、运行依赖、开发依赖及忽略 `.venv/`、`.env`、`.cache/`、缓存和构建产物的规则。模型字段允许合理自定义，但未知拼写字段应拒绝，避免静默忽略。
- [x] **Step 4:** 执行 `uv run python -m pytest tests/test_schemas.py -q`，预期全部通过；执行 `uv lock`，确认生成可复现依赖锁。
- [ ] **Step 5:** 若已有仓库，提交该任务的源码、测试、项目配置和锁文件，消息为 `feat: define reusable copywriting contracts`。 （本次不适用：目录不是 Git 仓库，未创建提交。）

## Task 2: 图片验证与供应商无关的模型接口

**Files:**
- Create: `src/ecommerce_copy_agent/images.py`, `src/ecommerce_copy_agent/adapters/__init__.py`, `src/ecommerce_copy_agent/adapters/base.py`
- Test: `tests/test_images.py`, `tests/test_adapter_contract.py`

**Interfaces:**
- Consumes: 任务 1 的 `ImageInput`、`TokenUsage` 和错误类型。
- Produces: `PreparedImage(data: bytes, media_type: str)`；`prepare_images(images: list[ImageInput]) -> list[PreparedImage]`。
- Produces: `ModelRequest(system_prompt: str, user_prompt: str, images: list[PreparedImage])`，`ModelResponse(text: str, model: str, usage: TokenUsage | None = None)`；温度和 token 上限等参数由具体适配器配置持有，不添加通用参数转换系统。
- Produces: `ModelAdapter` Protocol，属性 `model_name: str`、`supports_images: bool`；方法 `async generate(self, request: ModelRequest) -> ModelResponse`。适配器不接受 LangGraph 状态或 GUI 对象。

- [x] **Step 1:** 添加 `test_chinese_path_image`，使用临时目录中的 `商品图.png` 并断言读取字节与格式正确；`test_image_limits` 断言 5 张及单张超过 `10 * 1024 * 1024` 字节失败；`test_invalid_image_inputs` 参数化损坏图片、伪扩展名、声明 MIME 不匹配、目录路径和不支持格式；`test_animated_image_rejected` 断言多帧图片失败；`test_decompression_bomb_rejected` 通过临时降低 Pillow 像素阈值验证明确的输入错误，不分配巨型图片。另写假适配器测试，断言标准请求可以不依赖 OpenAI SDK 构造与调用。
- [x] **Step 2:** 执行 `uv run python -m pytest tests/test_images.py tests/test_adapter_contract.py -q`，确认因缺少模块而失败。
- [x] **Step 3:** 实现模型接口和图片验证；本地文件先检查大小，再以有上限的读取方式读取，使用 Pillow 验证实际内容、尺寸安全及单帧要求。文件后缀存在时应与实际格式相容（`.jpg` 和 `.jpeg` 等价）；字节来源以声明 MIME 对照实际格式。不可读文件统一抛出安全的 `InputError`。图片内容类的 repr 不展示字节。
- [x] **Step 4:** 执行上述测试，预期全部通过。
- [ ] **Step 5:** 若已有仓库，提交任务文件，消息为 `feat: validate images and define model adapter protocol`。 （本次不适用：目录不是 Git 仓库，未创建提交。）

## Task 3: 可配置的 OpenAI 兼容适配器

**Files:**
- Create: `src/ecommerce_copy_agent/config.py`, `src/ecommerce_copy_agent/adapters/openai_chat.py`, `.env.example`
- Test: `tests/test_config.py`, `tests/test_openai_chat.py`

**Interfaces:**
- Consumes: 任务 2 的标准模型请求、响应和协议。
- Produces: `ModelConfig(provider: str = "openai_chat", base_url: str, api_key: SecretStr, model: str, supports_images: bool = False, timeout_seconds: float = 60, temperature: float | None = None, max_tokens: int | None = None)`。此类型只属于内置 OpenAI Chat 配置路径，`max_tokens` 只对应这个适配器的当前协议映射；未知 provider 的拒绝只作用于该加载器，不限制 `CopywritingAgent` 注入其他适配器。其他协议可以自行定义配置类型。
- Produces: `load_model_config(values: Mapping[str, object] | None = None) -> ModelConfig`；显式值优先，缺失项读取 `COPY_AGENT_BASE_URL`、`COPY_AGENT_API_KEY`、`COPY_AGENT_MODEL`、`COPY_AGENT_SUPPORTS_IMAGES`、`COPY_AGENT_TIMEOUT_SECONDS`。显式空值视为配置错误，不偷偷回退。
- Produces: `OpenAIChatAdapter(config: ModelConfig, *, transport_factory: Callable[[], httpx.AsyncBaseTransport] | None = None)`，实现 `ModelAdapter`；该工厂仅作为测试注入点。每次 `generate` 通过工厂创建新的 transport，并创建、关闭本次异步 HTTP 客户端；适配器拥有并关闭此次生成的 transport，工厂不得返回已使用或共享实例。默认路径使用 SDK 的独立客户端，避免同步多次调用复用已关闭的事件循环，也不为首版引入连接池生命周期接口。

- [x] **Step 1:** 用返回新 MockTransport 的工厂捕获 HTTP 请求。`test_multimodal_payload_and_custom_endpoint` 断言指定模型、`/v1/chat/completions` 路径、图片 data URL 与文本正确；`test_optional_parameters_omitted` 断言未配置时不发送 temperature、max_tokens、tools 或 response_format；`test_configured_generation_parameters_forwarded` 断言明确配置的温度和 token 上限准确进入该适配器的请求；`test_image_capability_required` 断言不支持图片时请求数为 0；`test_api_error_does_not_leak_secret` 在远端错误正文植入测试密钥，断言公开异常字符串和 traceback 不含它；`test_no_transport_retries` 参数化超时、401、429、500 并断言仅调用一次；`test_optional_usage` 断言无 usage 时为 `None`；`test_transport_created_and_closed_per_call` 断言连续调用创建不同 transport，各自恰好关闭一次，调用已关闭的测试 transport 应立即失败。配置测试覆盖显式值优先、无效布尔值、空密钥、非法 URL scheme、URL 内嵌凭据和非正超时。
- [x] **Step 2:** 执行 `uv run python -m pytest tests/test_config.py tests/test_openai_chat.py -q`，确认预期失败。
- [x] **Step 3:** 实现配置和适配器。使用 `AsyncOpenAI`，指定 `max_retries=0`、超时及自定义 base URL，默认保留 TLS 验证。模型消息转换为 system 和 user 的图文内容；响应缺少 choice 或 content 不是字符串时用安全的模型服务错误终止，空字符串则交给工作流检查并修正。服务异常使用 `raise ... from None`，避免将包含远端正文的 SDK 异常链泄露给调用方。配置模型启用 `hide_input_in_errors=True`，公开配置异常不附带原始输入；配置未知 provider 时明确报错。`.env.example` 只放占位符，并注明程序读取进程环境，不自动加载 `.env` 文件。
- [x] **Step 4:** 执行上述测试，预期全部通过；检查配置 repr 中密钥已遮挡，成功响应的原始厂商对象未透出适配器。
- [ ] **Step 5:** 若已有仓库，提交任务文件，消息为 `feat: add configurable OpenAI-compatible adapter`。 （本次不适用：目录不是 Git 仓库，未创建提交。）

## Task 4: LangGraph 流程与独立调用入口

**Files:**
- Create: `src/ecommerce_copy_agent/prompts.py`, `src/ecommerce_copy_agent/validation.py`, `src/ecommerce_copy_agent/workflow.py`, `src/ecommerce_copy_agent/agent.py`
- Modify: `src/ecommerce_copy_agent/__init__.py`
- Test: `tests/test_workflow.py`, `tests/test_agent.py`

**Interfaces:**
- Consumes: 前三项任务定义的公共类型、图片验证和 `ModelAdapter`。
- Produces: `build_model_request(request: CopyRequest, images: list[PreparedImage], *, previous_text: str | None = None, problems: list[str] | None = None) -> ModelRequest`。
- Produces: `ValidatedCopy(text: str, warnings: list[str])`；`validate_output(raw: str, requirements: CopyRequirements) -> ValidatedCopy`，不合格时抛出带安全问题列表的 `OutputValidationError`。
- Produces: `build_workflow(model: ModelAdapter) -> CompiledStateGraph`；状态包含当前请求、已准备图片、最新模型文本、检查问题、累计用量、请求次数和最终结果，全部以每次调用的新状态初始化。
- Produces: `CopywritingAgent(model: ModelAdapter)`；`generate(self, request: CopyRequest) -> CopyResult`、`async agenerate(self, request: CopyRequest) -> CopyResult`。同步入口发现当前线程已有运行中的事件循环时，抛出提示使用 `agenerate` 的公开错误；创建 coroutine 前完成该判断。

- [x] **Step 1:** 编写确定性的假适配器测试。`test_first_response_valid` 断言一轮成功且调用次数为 1；`test_repair_once` 提供一次非法输出和一次有效输出，断言次数为 2；`test_repair_preserves_context` 断言第二次请求仍包含原始商品资料、要求和完全相同的图片字节，且加入上一结果及检查问题；`test_repair_exhausted` 断言第二次失败后无第三次调用；`test_service_error_skips_repair` 断言服务异常立即结束；`test_custom_adapter_without_vision_rejected_before_call` 断言核心对不支持图片的自定义适配器不发起调用，无需实例化 `ModelConfig`；`test_bad_output_shapes` 参数化空白正文、非对象 JSON、缺失 warnings、非字符串警告和超长正文；`test_usage_accumulation` 断言完整用量逐项相加，任一缺失则整体为 `None`；`test_concurrent_requests_isolated` 用可并发的假适配器检查商品信息和状态互不串用；`test_repeated_sync_calls` 断言同一实例连续同步调用成功；`test_real_adapter_repeated_sync_calls` 使用真实 `OpenAIChatAdapter` 与每次新建的模拟 HTTP transport，断言同一 Agent 跨两次同步事件循环正常返回且 transport 均被关闭；`test_sync_rejected_inside_event_loop` 断言有明确错误且无未 await 警告；`test_no_gui_import_in_core` 用独立进程断言导入核心后 `tkinter` 不在 `sys.modules` 中。
- [x] **Step 2:** 执行 `uv run python -m pytest tests/test_workflow.py tests/test_agent.py -q`，确认因缺少实现而失败。
- [x] **Step 3:** 实现提示和本地验证。用户资料以数据区域明确包裹，不拼入系统规则；明确禁止无依据的材质、功效、认证和优惠声明。只接受一个 JSON 对象；允许去除完整包裹的 JSON 代码围栏，不从任意文本中猜测截取 JSON。不合格输出的错误不得包含整段原始文案或图片。
- [x] **Step 4:** 实现图节点及条件路由，修正时仍保留原始图片、要求和事实资料；次数在实际调用前递增，所有业务状态来自调用输入，图中不得保存可变的全局当前请求。实现同步/异步入口和公共导出。错误输入在请求模型之前失败；输出 model 使用配置模型名称。
- [x] **Step 5:** 执行 `uv run python -m pytest tests/test_workflow.py tests/test_agent.py -q`，预期全部通过；再执行 `uv run python -m pytest tests -q` 检查前四个任务的契约集成。
- [ ] **Step 6:** 若已有仓库，提交任务文件，消息为 `feat: implement bounded LangGraph copywriting workflow`。 （本次不适用：目录不是 Git 仓库，未创建提交。）

## Task 5: 最简桌面测试工具

**Files:**
- Create: `desktop/__init__.py`, `desktop/__main__.py`, `desktop/app.py`, `desktop/forms.py`, `docs/product-design.md`, `AGENTS.md`
- Test: `tests/test_desktop_forms.py`, `tests/__init__.py`, `tests/manual/__init__.py`, `tests/manual/desktop_smoke.py`

**Interfaces:**
- Consumes: `CopyRequest`、`ProductInfo`、`CopyRequirements`、`FileImage`、`ModelConfig`、`OpenAIChatAdapter`、`CopywritingAgent.generate`。
- Produces: `parse_attributes_json(text: str) -> dict`，空白视为 `{}`，非对象或不支持的属性值明确失败；`build_request(values: Mapping[str, str], image_paths: list[Path]) -> CopyRequest`。
- Produces: `CopyAgentWindow(root: tkinter.Tk, *, agent_factory: Callable[[ModelConfig], CopywritingAgent] | None = None)`；`main() -> None`。测试通过工厂注入假 Agent，生产默认使用真实适配器，不提供伪生成开关。

- [x] **Step 1:** 添加表单行为测试：`test_invalid_attributes_json` 断言格式错误与 JSON 数组得到可读的输入错误；`test_form_maps_custom_requirements` 断言自定义文案类型、中文属性、最大字符数与文件列表正确进入核心请求。执行 `uv run python -m pytest tests/test_desktop_forms.py -q` 并确认失败。
- [x] **Step 2:** 实现表单和单窗口界面。商品名称、属性 JSON、补充描述、图片列表、文案类型与写作要求集中在输入区；API 地址、模型、遮挡的密钥和视觉能力选项集中在模型区；结果正文、提示和复制按钮在输出区。简单字段保留合理默认值，较长内容支持滚动，适配常见 Windows 显示缩放。
- [x] **Step 3:** 实现 `daemon=True` 的后台线程与 `queue.Queue` 结果交接，主线程通过 `root.after` 轮询。提交时对表单取快照；工作线程只持有请求、Agent 和队列，不捕获窗口对象、不访问 Tkinter。生成中禁用提交与复制；新调用开始清除旧结果；失败保留输入并恢复提交。关闭时设置关闭状态并取消主线程轮询，销毁窗口，不 join 网络线程；`mainloop` 返回后主进程可退出。关闭窗口并不保证远端已接受的模型请求被取消，界面不承诺取消请求。
- [x] **Step 4:** 执行表单测试，预期通过。创建显式运行的桌面冒烟模块，用延迟假 Agent 驱动真实 Tk 控件，验证生成中状态、重复提交防护、成功复制、失败后无旧结果可复制，以及生成中关闭窗口无 Tcl 异常。使用两个退出场景：同进程中等候一次后台结果并确认销毁后不写控件；子进程中用事件阻塞假生成调用，关闭窗口后断言进程在 5 秒内自行退出。执行 `uv run python -m tests.manual.desktop_smoke`；只有实际断言通过才记为通过。
- [x] **Step 5:** 启动 `uv run python -m desktop` 检查窗口启动；可用的 UI 工具支持时检查布局和交互，否则保留启动及脚本检查结果，并把人工视觉检查标为未验证。将原生控件、明确字段标签、状态反馈和复制语义写入 `docs/product-design.md`，在 `AGENTS.md` 链接该文档及设计文档。
- [ ] **Step 6:** 若已有仓库，提交任务文件，消息为 `feat: add minimal Tkinter agent test app`。 （本次不适用：目录不是 Git 仓库，未创建提交。）

## Task 6: 调用示例、安装验证与交付

**Files:**
- Create: `examples/generate_copy.py`, `examples/generate_copy_async.py`, `examples/model-config.example.json`, `README.md`, `tests/test_package_smoke.py`
- Modify: `pyproject.toml`（仅修正打包发现问题）、`docs/superpowers/plans/2026-09-30-ecommerce-copy-agent.md`（记录结果）

**Interfaces:**
- Consumes: 已导出的 `CopywritingAgent`、请求类型、`ModelConfig`、`OpenAIChatAdapter`、`load_model_config`。
- Produces: 可安装 wheel、无 GUI 同步/异步调用示例，以及从非敏感 JSON 配置和环境密钥构建模型的说明。

- [x] **Step 1:** 编写 `test_public_api_smoke`，只通过公共导出和假适配器完成一次请求，断言结果可以 `model_dump_json()`、只包含约定字段、没有密钥或图片内容。执行 `uv run python -m pytest tests/test_package_smoke.py -q`；若已有功能使其直接通过，将其记为集成验证，不制造无意义失败。
- [x] **Step 2:** 添加同步/异步示例和非敏感 JSON 配置例子。示例从本地环境获取密钥，不要求将密钥发送到聊天中；缺少配置时明确退出，不触发真实网络请求。README 写清安装、启动桌面、嵌入其他 Python 程序、传入图片、环境变量、适配器扩展和字符计数语义。
- [x] **Step 3:** README 说明默认图片能力关闭、需要自行启用并实际验证；`.env.example` 不自动加载；本地校验不等于事实审核；失败和调用上限可预期。提供纯文本及含图两条真实中转站验证步骤，未提供本地配置时标记未执行。
- [x] **Step 4:** 执行 `uv run python -m pytest tests -q`，预期全部自动化测试通过；执行 `uv build`，预期生成 wheel 和源码包；创建临时独立环境安装生成的 wheel，从项目目录之外运行假适配器同步/异步示例，确认不依赖源目录、桌面目录或工作目录。
- [x] **Step 5:** 若本机已有用户提供的有效配置，在不输出密钥的前提下运行纯文本和含图集成测试；否则记录真实 API 未验证。执行一次最终代码审查，重点检查适配器边界、两次调用上限、错误脱敏、状态隔离和桌面关闭行为；对发现的问题修复后只重跑相关检查及必要集成测试。
- [ ] **Step 6:** 若已有仓库，提交任务文件，消息为 `docs: add integration examples and verified setup guide`。向用户交付启动命令、主要文件、已执行的验证结果和未验证项，不声称已完成未执行的真实 API 或视觉测试。 （本次不适用：目录不是 Git 仓库，未创建提交。）

## 自审结果与执行交接

- 设计第 1–3 节对应任务 1、2、4、6；模型配置对应任务 3；流程对应任务 4；桌面工具对应任务 5；错误和敏感信息要求贯穿任务 1、3、4；验收对应各任务测试和任务 6。
- 任务之间的数据类型与调用名称保持一致；配置属于适配器，图片属于请求，桌面仅使用公开接口。
- Review Focus 的五类问题均有明确的归属测试或桌面检查；真实 API 与人工视觉检查允许条件性未验证，但必须报告。
- 用户已确认独立审查后的计划，并要求拆分给多个 Agent 推进。执行安排：基础 Agent 依次完成任务 1、2；桌面与文档 Agent 在独立文件内先行工作；基础接口就绪后，模型适配器与工作流分别交给 Agent 实现；主 Agent 负责接口协调、独立审查安排、最终集成与安装验证。进度记录在 `.superpowers/sdd/ecommerce-copy-agent/progress.md`。

## 独立审查修订记录（2026-09-30）

- 已核实并修正生成参数职责不一致：选择适配器持有配置，同步澄清设计文档，不新增通用参数系统。
- 前置 Tkinter 运行时与窗口初始化检查，并补充受限环境的临时 uv 缓存用法。
- 测试改用模块入口，避免桌面源码不在 wheel 中造成导入路径不确定。
- 明确每次调用创建并关闭 transport，以及桌面后台线程的退出语义；补充真实适配器的模拟 HTTP 生命周期验证。
- 明确内置配置加载器不限制自定义适配器；增加修正上下文保留与核心图片能力检查的验证。
- 以上为文档一致性和执行风险修订；测试仍是待实施任务，不代表产品测试已经运行或通过。
- 同一独立审查 Agent 已针对修订点复核，确认原五项意见在文档层面关闭，未发现修订引入新的明显矛盾或执行阻碍。
