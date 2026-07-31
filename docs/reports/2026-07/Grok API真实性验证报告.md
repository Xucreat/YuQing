# Grok API 真实性验证报告

## Phase

Phase Grok-Key-Validation

## 执行约束

- 仅执行一次真实 API 请求
- 未修改业务代码
- 未修改配置
- 未接入 CollectorService
- 未启用 `data_sources.grok_search`
- 未访问数据库
- 未写入 Opinion、Risk、Event 或 AI 链路
- 未创建测试文件

## 只读配置审计

- 配置读取方式：现有 `Settings`，读取项目 `.env`
- `GROK_API_KEY`：已配置，但有效性验证失败
- `GROK_BASE_URL`：`https://api.x.ai/v1`
- `GROK_MODEL`：`grok-4.20`
- `GROK_PROXY`：已配置，HTTP 代理 `127.0.0.1:7897`
- `httpx`：`0.27.2`
- `openai`：`1.45.0`
- OpenAI SDK Responses API：当前版本不提供 `responses` 接口

## 唯一真实请求

- 方法：`POST`
- 路径：`/v1/responses`
- 请求模型：`grok-4.20`
- 输入：`测试关键词：廊坊`
- 工具：`web_search`
- 请求次数：1

## 验证结果

- HTTP 状态：`400`
- 错误原因：`Incorrect API key provided`
- 是否为 Key 问题：是
- 是否为模型问题：否，鉴权失败发生在模型验证之前
- 是否为代理问题：否，代理请求已到达 xAI 并收到标准 API 响应
- 是否获得 `usage`：否
- 是否获得 `output`：否
- 是否获得 `url_citation`：否

## 结论

本次验证失败，停止后续验证。

当前不能确认：

- `grok-4.20` 是否可用
- Responses API 返回结构
- `usage` 成本字段
- `web_search` citation 结构

等待新的有效 `GROK_API_KEY` 后再重新执行一次验证。
