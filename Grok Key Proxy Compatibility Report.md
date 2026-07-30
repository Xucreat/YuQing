# Grok Key / Proxy Compatibility Report

## 审计范围

- 只读检查 `.env`、`Settings`、依赖版本和部署配置
- 未修改代码、配置或数据库
- 未创建 migration
- 未发起新的真实 API 请求
- 未接入任何业务链路

## 当前链路图

```text
项目根目录 .env
    │
    ├── GROK_API_KEY ───────────────┐
    └── GROK_PROXY ───────────────┐ │
                                  ▼ ▼
app/core/config.py Settings
    │
    ├── GROK_BASE_URL 缺省
    │      └── 默认 https://api.x.ai/v1
    │
    ├── GROK_MODEL 缺省
    │      └── 默认 grok-4.20
    │
    └── httpx.Client(proxy=GROK_PROXY, trust_env=True)
                         │
                         ▼
              POST https://api.x.ai/v1/responses
                         │
                         ▼
                 本地 HTTP 中转 127.0.0.1:7897
                         │
                         ▼
                       xAI API
```

## 配置来源

- `.env` 实际配置了：
  - `GROK_API_KEY`
  - `GROK_PROXY`
- `.env` 未配置：
  - `GROK_BASE_URL`
  - `GROK_MODEL`
- `GROK_BASE_URL` 当前来自 [config.py](C:/Users/Administrator/Desktop/YQ/backend/app/core/config.py) 默认值：
  - `https://api.x.ai/v1`
- `GROK_MODEL` 当前来自配置默认值：
  - `grok-4.20`

## Key 格式审计

- Key 已配置
- 长度：67
- ASCII：是
- 首尾空白：无
- 外层引号：无
- 占位符特征：无
- `xai-` 前缀：未检测到
- 类型判断：opaque token，无法仅凭格式确认来源

xAI 官方示例使用 `XAI_API_KEY`，并展示 `xai-...` 形式的 Key。当前 Key 不具备该格式特征，属于高度可疑状态，但格式本身不能单独证明 Key 一定无效。

## 实际请求结果

上一轮唯一真实请求使用：

- 目标：`https://api.x.ai/v1/responses`
- 方法：`POST`
- 模型：`grok-4.20`
- 工具：`web_search`
- 代理：`127.0.0.1:7897`
- HTTP 状态：`400`
- 错误：`Incorrect API key provided`

## 兼容性判断

### Base URL

当前 Base URL 与官方 API 根路径一致，未发现需要修改的证据。

判断：**当前 Base URL 正确，暂不修改。**

### Proxy

上一轮请求经由 `127.0.0.1:7897` 后能够收到 xAI API 返回的鉴权错误，说明：

- 本地代理端口可连接
- HTTP 请求已被代理转发
- 目标路径至少在传输层可达

但由于鉴权在服务端提前失败，无法确认代理后的链路是否完整支持：

```text
POST /v1/responses
tools = [{"type": "web_search"}]
```

应用层 Web Search 兼容性：**未知**。

### OpenAI SDK

- 当前 `openai==1.45.0`
- 当前 SDK 不提供 `OpenAI.responses`
- 当前验证路径使用已有 `httpx`
- 不建议升级 OpenAI SDK

## 失败原因

主要失败原因是 API Key 无效、错误类型或已失效，而不是当前 Base URL 或代理连接问题。

不能排除的次要可能性：

- Key 来自其他平台或其他 API 产品
- Key 已撤销或过期
- Key 复制时缺少内容
- Key 与当前 xAI 账户/项目不匹配
- 当前中转服务改写了 Authorization 头

其中最后一项目前无法仅凭一次 `Incorrect API key` 响应确认。

## 决策

- 是否需要更换 Key：**是，优先更换为 xAI 控制台生成的有效 API Key**
- 是否需要修改 Base URL：**目前不需要**
- 是否需要修改代理：**主机验证暂不需要；Docker 容器内的 127.0.0.1 代理可达性仍未知**
- 是否建议继续接入：**暂不建议**

等待有效 Key 后，应只重新执行一次相同的最小请求，先确认：

1. HTTP 200
2. Responses `output`
3. `usage`
4. `url_citation`
5. `web_search` 工具是否真正执行
