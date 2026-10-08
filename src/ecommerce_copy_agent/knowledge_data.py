"""Locally curated guidance, editorially summarized from the cited pages.

These are source-grounded writing principles, not product facts or a live feed.
The retrieval date and reading notes are recorded in docs/marketing-sources.md.
"""

CURATED_KNOWLEDGE: tuple[dict[str, object], ...] = (
    {
        "id": "K01",
        "title": "广告主张先核实事实依据",
        "url": "https://www.ftc.gov/business-guidance/resources/advertising-faqs-guide-small-business",
        "summary": "广告中的明确或暗示性功效、性能、安全、价格等主张，都可能影响购买决定。写文案时先核对商品资料和可用证据；没有依据的承诺应删除或标为待核实。该美国指南提供的是核实思路，不能替代目标市场的法律审查。",
        "tags": ["通用", "事实", "证据", "context:功效", "context:性能", "context:认证"],
        "accessed_on": "2026-09-30",
    },
    {
        "id": "K02",
        "title": "用已知属性支撑购买利益",
        "url": "https://www.shopify.com/enterprise/blog/seo-product-descriptions",
        "summary": "商品属性说明产品有什么，利益说明该属性怎样帮助使用者。可以先写与购买决定有关的利益，再用用户提供的具体属性支撑；属性无法证明的效果不要推断。",
        "tags": ["通用", "利益", "copy_type:卖点描述", "copy_type:详情介绍"],
        "accessed_on": "2026-09-30",
    },
    {
        "id": "K03",
        "title": "避免空泛夸张的营销口吻",
        "url": "https://www.nngroup.com/articles/how-users-read-on-the-web/",
        "summary": "NN/g 的网页阅读研究指出，读者倾向快速寻找直接信息，对夸张、主观的促销用语反感。文案宜用可核实的商品细节和自然语言表达，少写没有根据的“最好”“爆款”等口号。",
        "tags": ["通用", "自然语言", "copy_type:宣传文案", "copy_type:社交平台文案"],
        "accessed_on": "2026-09-30",
    },
    {
        "id": "K04",
        "title": "让较长页面便于扫读",
        "url": "https://www.nngroup.com/articles/how-users-read-on-the-web/",
        "summary": "网页读者常先扫读。较长的商品介绍可让小标题点明信息、一段集中一个意思、重要结论提前，并删去重复句；短标题不必套用长文结构。",
        "tags": ["通用", "copy_type:详情介绍", "context:移动端"],
        "accessed_on": "2026-09-30",
    },
    {
        "id": "K05",
        "title": "按购买问题决定信息量",
        "url": "https://www.shopify.com/enterprise/blog/seo-product-descriptions",
        "summary": "商品说明没有统一的理想长度。对不熟悉的产品或需要比较的购买决定，可以补充已知的用途、适配、尺寸、使用或护理信息；简单商品可以更简短。缺失的细节应列为待补信息。",
        "tags": ["通用", "copy_type:详情介绍", "audience:新手"],
        "accessed_on": "2026-09-30",
    },
    {
        "id": "K06",
        "title": "商品页关键词保持准确自然",
        "url": "https://www.shopify.com/enterprise/blog/seo-product-descriptions",
        "summary": "独立站商品页应先回答购买者想知道的商品信息。标题和描述可使用与真实商品相符的搜索用语，但不要生硬重复关键词；不同展示位置需按空间和用途调整文案。",
        "tags": ["platform:独立站", "copy_type:商品标题", "copy_type:详情介绍", "context:搜索"],
        "accessed_on": "2026-09-30",
    },
)
