# 国外数据源 RSS 接入推荐清单

> 配套本次修复：新增/编辑外网数据源弹窗的「RSS 地址」已改为多行文本框，支持**换行或逗号**分隔多个地址（每行一个）。
> 本文为接入参考，非系统源码，未纳入提交；可随时删除。

## 一、前提：境外抓取依赖代理（务必先看）
本系统抓取境外站依赖环境变量 `FOREIGN_HTTP_PROXY`（运行环境默认指向 `127.0.0.1:7897`）。
若服务器上该代理未启动或不可达：
- 连通性测试会显示「测试通过：列表页获取到 0 个链接」——**这是假通过，掩盖了真实网络故障**，并非配置错误。
- 排查：在服务器侧确认 `HTTP_PROXY` / `HTTPS_PROXY` 指向可达的境外代理后重试。

## 二、最灵活稳定的方案：Google News 关键词 RSS
可按关键词实时聚合多源，最适合定向监控（如涉华、涉湖北舆情）：
- 湖北相关：`https://news.google.com/rss/search?q=Hubei&hl=en-US&gl=US&ceid=US:en`
- 通山/中国：`https://news.google.com/rss/search?q=Tongshan+China&hl=en-US&gl=US&ceid=US:en`
- 自定义：`https://news.google.com/rss/search?q=<关键词>&hl=en-US&gl=US&ceid=US:en`

## 三、推荐媒体 RSS（英文为主，国际公信力高）
| 媒体 | RSS 地址 | 覆盖侧重 | 备注 |
|------|----------|----------|------|
| BBC World | `http://feeds.bbci.co.uk/news/world/rss.xml` | 全球 / 中国 | 稳定，英文 |
| The Guardian World | `https://www.theguardian.com/world/rss` | 全球 / 中国 | 稳定 |
| Al Jazeera | `https://www.aljazeera.com/xml/rss/all.xml` | 全球 / 中东 | 全量 |
| New York Times World | `https://rss.nytimes.com/services/xml/rss/nyt/World.xml` | 全球 / 中国 | 需网络可达 |
| CNN World | `http://rss.cnn.com/rss/edition_world.rss` | 全球 | |
| DW English | `https://rss.dw.com/rdf/rss-en-all` | 欧洲 / 全球 | |
| France 24 English | `https://www.france24.com/en/rss` | 欧洲 / 非洲 / 全球 | |
| VOA World (English) | `https://www.voanews.com/api/zytcms/rss/world-english` | 全球 / 中国 | |
| NPR World | `https://feeds.npr.org/1004/rss.xml` | 美国 / 全球 | |
| ABC News (Australia) | `https://www.abc.net.au/news/feed/51120/rss.xml` | 亚太 | |
| South China Morning Post (China) | `https://www.scmp.com/rss/91/feed` | 中国深度 | 香港英文媒体，中国议题覆盖最佳（建议先测可达性） |
| SCMP World | `https://www.scmp.com/rss/2/feed` | 国际 | |
| TechCrunch | `https://techcrunch.com/feed/` | 科技 | |
| The Verge | `https://www.theverge.com/rss/index.xml` | 科技 | |

> 注：Reuters 已停止公共 RSS，建议用「Google News 关键词」替代。各源 RSS 路径偶有调整，录入前用弹窗「连通性测试」验证一次即可。

## 四、录入与评分注意事项
- 每个地址必须是 `http/https` 开头；系统有 SSRF 防护，会拦截内网/非常规地址。
- 测试建议先单地址验证可达，再批量粘贴多行。
- **地域准入语义**：国外源内容按 `foreign_keywords`（敏感词类型）评分，严格的「通山 / 13 乡镇」地域词对英文原文几乎不会命中。若目标是监控涉华/涉湖北舆情，应在「国外关键词」里配置相应敏感词，而非依赖地域词。
- 代理环境变量默认 `FOREIGN_HTTP_PROXY`，可在弹窗「代理环境变量」字段调整。

## 五、可选下一步
需要我直接帮你把其中几个源（如 SCMP + BBC + Google News 湖北）录入系统吗？我可以通过 API 创建并立即跑一次连通性测试（前提是服务器代理可达）。
