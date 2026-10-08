# 本地营销知识来源

默认 `LocalKnowledgeRetriever` 使用六张人工整理的中文知识卡。检索只在本地卡片中按请求上下文排序，不会访问互联网，也不把模型记忆当作检索结果。工作流决定送入策划阶段的卡片数量与摘要总长度。

以下页面于 **2026-09-30** 通过 HTTP 成功取得并核对相关正文。卡片摘要是本项目撰写的中文转述，**不是原文引语**，不能作为商品事实的证据。

| 卡片 | 核对的公开页面 | 实际核对的要点 |
| --- | --- | --- |
| K01 | [FTC — Advertising FAQ's: A Guide for Small Business](https://www.ftc.gov/business-guidance/resources/advertising-faqs-guide-small-business) | 页面说明美国广告主张应真实、有依据；评估包括明确及暗示性主张，以及影响购买决定的性能、安全、价格等信息。这里仅借鉴“主张应有事实依据”的通用编辑原则。**美国 FTC 指南不是中国平台的法律或合规标准**，也不能代替适用地区的专业审查。 |
| K02、K05、K06 | [Shopify — SEO Product Descriptions: 7 Tips To Optimize Your Product Pages](https://www.shopify.com/enterprise/blog/seo-product-descriptions) | 页面建议先面向购物者写作，用属性支撑利益，按商品复杂度和购买问题决定长度，准确且自然地使用搜索词，并适配不同展示位置。原先的 `/blog/product-descriptions` 链接访问时跳转到此页；卡片记录最终页面 URL。未采用页面中的流量、点击率或转化数据。 |
| K03、K04 | [NN/g — How Users Read on the Web](https://www.nngroup.com/articles/how-users-read-on-the-web/) | 页面说明网页读者常扫读，建议明确的小标题、一段一个意思、重要信息提前，并指出读者反感空泛夸张的促销语言。该研究关于网页阅读与可用性，**不证明这些建议能提高本项目文案的销售转化**。 |

卡片中的“利益”必须由请求中已知的商品属性支撑。页面是写作方法来源，不授权补造产品材质、功效、认证、价格、优惠或用户评价；信息不足时应提出待核实项。

`KnowledgeRetriever` 是可替换的异步协议。要接入实时搜索，调用方自行实现 `async retrieve(request: CopyRequest) -> list[KnowledgeSource]`，返回带有效 HTTP(S) URL、来源、访问日期和编辑摘要的 `KnowledgeSource` 对象，然后通过 `CopywritingAgent(model, retriever=custom_retriever)` 注入。在线检索服务的请求、权限和错误处理由该实现负责；工作流仍会对真正送入策划的来源做数量、摘要长度、去重和有效性检查。`LocalKnowledgeRetriever(sources=[...])` 也可用于注入自备的静态卡片。

实时检索返回的条目必须显式设置 `origin="web"`；自备静态资料使用 `origin="custom"`，经过整理的本地知识卡使用 `origin="curated"`。模型默认值为 `curated`，因此在线接入不能省略该字段。桌面按这个标记展示资料类型，不会从 URL 猜测是否实时联网。
