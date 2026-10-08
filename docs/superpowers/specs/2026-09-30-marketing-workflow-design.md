# 营销文案工作流升级

依据：用户反馈文案生硬、缺乏扩写与专业营销策略；2026-09-30 用户授权“按你的理解继续推进”。本文替代首版设计中的单次生成、两次调用上限与无资料检索约束，其余接口、图片、保密和桌面约束保留。

## 目标

在保留 Python 库、LangGraph、任意模型适配器、简单 Tkinter 客户端的前提下，使每次生成实际经历资料检索、营销策划、初稿、编辑审查、定稿。商品品类不固定；输入稀少时明确假设与信息缺口，不编造商品事实。多轮调用是工作机制，不代表保证销量提升。

## 流程

1. 本地验证图片与模型能力，再检索营销知识。默认从附来源的本地资料按平台、文案类型、品类选择；不把模型记忆称为联网检索。
2. 策略阶段整理已知事实、受众假设、购买动机、主张、属性对应利益、场景、顾虑、行动目标、缺失信息与引用编号。
3. 初稿阶段实际展开策略中的具体场景和利益，避免通用品质口号；不为短标题强塞长篇结构或行动号召。
4. 编辑阶段输出引用原句的具体问题与修改建议，以及事实风险。审查不是认证或预测转化率。
5. 定稿阶段始终消费初稿和审稿结果，改写正文。最后仍检查 JSON、类型、正文和用户字数上限。

每阶段保留原始商品事实，图片可见特征不能推断材质、认证、价格或功效。检索资料及中间稿均为不可信数据，不能覆盖系统指令。引用只能从检索到的编号映射，未知编号必须纠正。没有适用资料时明确提示，不伪造引用。

审稿问题的 quote 必须是初稿实际存在的原句或片段，否则修复审稿输出。存在具体审稿问题时，完全未改动的定稿不能通过检查；没有问题时允许保留原稿。这只能检查最基本的实质编辑行为，不能证明所有问题均已解决。提示中明确每个字段的结构，避免让模型猜测字符串与数组类型。

### 0.2.1：针对实际失败文案的编辑修正

用户提供的“索尼游戏手柄”成稿把发布平台、品牌筛选、内部比较分析和未提供参数写成广告。修正保持现有接口与四阶段结构：平台是写作渠道，不是上架证据；创意场景、节奏、比喻与情绪邀请可自由创作，但不增加性能事实。资料少时写简短的品类广告，把未知参数留在 warnings，不把资料核对任务交给消费者当正文。

对常见中文宣传类输出增加狭窄的本地编辑检查，识别把“品牌信息明确、便于纳入比较、按品牌筛选”当卖点，以及泛化“请以商品详情页为准”的占位说明。检查发现的问题加入审稿并驱动改写；定稿仍有问题时使用现有修复预算，耗尽明确失败，不填入预写广告。用户提供的事实/明确要求的披露、已知兼容和安全限制必须保留。选购指南、客服说明等非广告类型不适用这些宣传检查。该启发式并不判断全部文案优劣，也不能认证事实。

## 公共接口

`CopywritingAgent(model, *, retriever=None, workflow_options=None)` 保留 generate/agenerate。ModelAdapter 和 ModelRequest 不变。

新增 `marketing.py`，定义 strict Pydantic 模型：

- `KnowledgeSource(id, title, url, summary, tags=[], origin="curated", accessed_on="")`：origin 为 curated/web/custom；URL 为有效 http/https，无用户密码。摘要是编辑整理的中文转述，不冒充原文引语。
- `MarketingStrategy(facts, audience_hypothesis, purchase_motivation, key_message, benefits, scenarios, objections, call_to_action, assumptions, missing_information, source_ids)`：全部字段必填，列表元素均字符串；audience_hypothesis/purchase_motivation/key_message 非空，其余字符串可为空，列表可为空。
- `ReviewIssue(quote, problem, suggestion)`：三个非空字符串。
- `EditorialReview(strengths, issues, factual_risks)`：列表，issues 为 ReviewIssue，其他为字符串。
- `WorkflowOptions(max_model_calls=6, timeout_seconds=300, max_sources=5, max_source_chars=12000)`：max_model_calls 4..12，timeout_seconds 有限正数，max_sources 1..10，max_source_chars 1000..30000；数字拒绝布尔值。

CopyResult 保留全部旧字段，增加默认值 `strategy: MarketingStrategy | None=None`、`draft: str=""`、`review: EditorialReview | None=None`、`sources: list[KnowledgeSource]=[]`。不返回隐藏推理或系统提示。

`knowledge.py` 定义 `KnowledgeRetriever` 协议 `async retrieve(request: CopyRequest) -> list[KnowledgeSource]`，以及 `LocalKnowledgeRetriever(sources=None)`。默认检索器返回排序后的资料，工作流负责限制资料数量与总摘要字符数、去重并检查来源有效性。自定义在线检索只实现该协议，不依赖任何模型的联网能力。返回 sources 是实际传给策划的资料，strategy.source_ids 是实际引用的子集。

## 预算与故障

正常四次模型调用，默认全流程最多六次，额外两次仅用于修复阶段结构或最终长度，避免无限循环。预留尚未执行阶段的调用额度，不让格式修复耗尽定稿所需调用。全流程包括检索有 300 秒默认超时，可配置；模型服务错误直接失败，输出不合格不能作为成功定稿。用量累计全部模型请求，任一缺失则总用量为 None。保持各次生成的状态隔离；未知异常公开信息不得泄露检索或模型凭据。

资料检索失败时明确抛出安全错误，让调用者修正服务；空资料允许继续但返回警告。结果 warnings 合并信息缺口、草稿/定稿提示和仍需核实的审查风险，不以模型自称通过消除风险。

## 界面

保留单窗口与正文复制，增加可切换的“营销策略 / 初稿 / 审稿 / 资料来源”查看区，明确默认使用本地资料，非实时联网。新请求或失败时清空旧产物，不复制策略或来源到宣传正文。多阶段耗时在状态提示中说明，不显示伪造的实时进度。

## 验收

- 假模型验证阶段传递、来源编号核验、审稿驱动定稿、预算、超时、并发隔离、图片与用量。
- 构造明确标注为模拟的跨品类样例：日用品、服饰、食品、数码、信息稀少、信息矛盾、短标题、长详情。
- 提供真实模型前后对比工具：同一输入与模型，旧单次流程对照新流程；记录调用、用量、耗时，人工比较事实可靠、商品具体性、购买理由、自然度和平台适配。无需用户提供商品样例；凭据留本机。
- 没有真实模型运行时，只报告离线流程验收，不宣称文案效果或转化率已经改善。
