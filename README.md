<div align="center">

# Prism

### A zero-dependency toolkit for building *resilient* LLM applications

Provider routing · semantic response caching · retries with backoff · circuit breaking · token/cost metering · a tool-calling agent — all on the Python standard library.

[✨ Why](#-why) · [🚀 Features](#-features) · [📦 Install](#-install) · [⚡ Quick Start](#-quick-start) · [🏗️ Architecture](#%EF%B8%8F-architecture) · [🔌 API](#-api) · [🧭 Roadmap](#-roadmap) · [📖 中文解读](#-中文解读可直接发文底稿)

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Dependencies](https://img.shields.io/badge/dependencies-zero-lightgrey)
![Platform](https://img.shields.io/badge/platform-CPython%20%2F%20PyPy-informational)
![Tests](https://img.shields.io/badge/tests-passing-success)

</div>

---

## ✨ Why

Calling an LLM is easy. Calling an LLM **reliably in production** is not. Real systems need to:

- **Survive rate limits and 5xx errors** without melting down.
- **Avoid paying twice** for the same prompt.
- **Spread load** across models and providers.
- **Fail fast** when a downstream dependency is unhealthy.
- **Know what it costs** in tokens and dollars.

Most libraries either lock you into a single vendor SDK or pull in a heavy dependency tree. **Prism** is a focused, ~1,000-line toolkit that gives you the resilience layer *around* any chat-completions provider — and it runs on nothing but the Python standard library, so you can drop it into any project, serverless function, or notebook without a `pip install` argument.

## 🚀 Features

- **Provider abstraction** — one `Provider` interface; ships with an OpenAI-compatible client (over `urllib`), plus offline `ScriptedProvider` and `EchoProvider` for tests and demos.
- **Smart routing** — `first`, `round_robin`, `lowest_cost`, `lowest_latency`, and `capability` strategies with per-provider metadata.
- **Semantic response cache** — deterministic, normalized keys so identical prompts hit the same entry; optional TTL.
- **Retry policy** — exponential backoff with jitter and a configurable set of retryable exceptions.
- **Circuit breaker** — opens after consecutive failures, fails fast, and probes recovery with a half-open state.
- **Observability** — per-call traces plus aggregate token and cost accounting.
- **Tool-calling agent** — a minimal ReAct-style loop that executes local tools and feeds results back to the model.
- **Zero dependencies** — pure standard library; Python 3.9+.

## 📦 Install

```bash
pip install prism-llm
```

Or copy the `prism/` package into your project — there is nothing to build.

```python
import prism
```

## ⚡ Quick Start

```python
from prism import Prism, Router, OpenAICompatibleProvider, user

provider = OpenAICompatibleProvider(api_key="sk-...", model="gpt-4o-mini")
prism = Prism(router=Router([provider]), use_cache=True, use_retry=True, use_breaker=True)

reply = prism.chat([user("Explain circuit breakers in one sentence.")])
print(reply.message.content)
print("tokens:", reply.usage.total_tokens)
```

**Expected output**

```
A circuit breaker stops sending requests to a failing service after a threshold
of errors, then periodically tests recovery so the system degrades gracefully.
tokens: 42
```

Offline, with the bundled `ScriptedProvider`:

```bash
python -m prism.cli demo
# or
python examples/demo.py
```

## 🏗️ Architecture

Prism is a thin facade that composes small, single-responsibility components around a provider.

```
┌──────────────────────────────────────────────┐
│                   Your App                    │
└───────────────────────┬──────────────────────┘
                        │
              ┌─────────▼─────────┐
              │       Prism        │   facade
              ├────────────────────┤
              │  Router            │  pick provider (rr / cost / latency / capability)
              │  SemanticCache     │  dedupe identical prompts (optional TTL)
              │  RetryPolicy       │  exponential backoff + jitter
              │  CircuitBreaker    │  fault isolation
              │  Meter             │  token / cost / latency traces
              └─────────┬──────────┘
                        │
              ┌─────────▼─────────┐
              │     Provider       │  OpenAICompatible / Scripted / Echo
              │  (chat/completions)│
              └────────────────────┘
```

Each layer is independently testable and can be swapped or removed.

## 🔌 API

| Component | Key method | Purpose |
|-----------|------------|---------|
| `Prism` | `chat(messages, tools=None, model=None, strategy=None, use_cache=True, stream=False)` | Run a completion through the full resilience stack. |
| `Prism` | `agent(messages, *, max_iter=5, model=None, system_prompt=None)` | Run the tool-calling agent loop. |
| `Prism` | `register_tool(func, *, name=None, description=None)` | Expose a Python function as a model tool (schema inferred from signature). |
| `Router` | `select(messages=None, tools=None, strategy=...)` | Choose a provider by the active strategy. |
| `SemanticCache` | `get / put(messages, model, tools)` | Store and retrieve completions by normalized key. |
| `RetryPolicy` | `run(fn, attempts=3, base_delay=0.2, backoff=2.0)` | Execute `fn` with backoff and jitter. |
| `CircuitBreaker` | `call(fn, failure_threshold=3, reset_timeout=10.0)` | Guard `fn` behind open/half-open/closed states. |
| `Meter` | `span / record / totals()` | Collect traces and aggregate usage. |
| `OpenAICompatibleProvider` | `complete / stream` | Speak the OpenAI Chat Completions protocol over `urllib`. |

### A tool-calling agent in a few lines

```python
from prism import Prism, Router, ScriptedProvider, user

prism = Prism(router=Router([ScriptedProvider("demo", script=[
    {"match": r"\d+\s*(times|\*)\s*\d+",
     "tool_call": {"id": "c1", "name": "multiply", "arguments": {"a": 7, "b": 5}}, "content": ""},
    {"after_tool": True, "content": "The product is 35."},
])]), cache=None)

@prism.register_tool(description="Multiply two integers.")
def multiply(a: int, b: int) -> int:
    return a * b

result = prism.agent([user("What is 7 times 5?")], max_iter=4)
print(result.answer)   # -> The product is 35.
```

## 🧭 Roadmap

- [ ] Async provider interface (`acomplete` / `astream`)
- [ ] Structured-output enforcement (JSON schema validation of `finish_reason`)
- [ ] Pluggable cache backends (Redis, SQLite)
- [ ] Prometheus exporter for the `Meter`
- [ ] Built-in small-embedding semantic cache (approximate near-duplicate prompts)
- [ ] Streaming aggregation with token-level cost estimation

## 🤝 Contributing

Bug reports, feature ideas, and pull requests are welcome. Keep changes covered by tests and run `python -m unittest discover -s tests` before opening a PR.

## 📄 License

Released under the [MIT License](./LICENSE).

---

## 📖 中文解读（可直接发文底稿）

> 下面这篇稿子本身就是一份可发布的内容底稿：它讲清了「解决什么问题」「核心原理」「关键实现点」「与同类方案对比」「如何扩展」，并附带「如何扩展成一篇发布稿」的提示。你可以直接复制到掘金 / 知乎 / 小红书 / B 站动态，按需补一两句个人口吻即可。

### 一、它解决什么问题？

把大模型接进业务，最开始大家都写一行 `requests.post` 调接口。但一上生产就露怯：

1. **限流与抖动**：供应商动不动回 429 / 500，你的接口跟着一起挂。
2. **重复烧钱**：同一个问题被反复问，每次都重新花钱算一遍。
3. **单点脆弱**：只接一家模型，对方一抖，你全抖。
4. **黑盒成本**：月底算账才发现 token 花了你半个月奶茶钱，却说不清花在哪。

Prism 就是把这些「周边工程」抽成一个薄薄的中间层，让你在「调模型」和「业务代码」之间多垫一层缓冲。

### 二、核心原理（四个小零件）

- **路由 Router**：一次请求该发给谁？轮询、最便宜、最低延迟、按能力（比如支不支持工具调用）选。本质是「负载均衡」的思想搬到了 LLM 上。
| **重试 RetryPolicy**：失败别立刻放弃，按 `base × backoff^attempt` 退避，再加一点随机抖动（jitter），避免一堆客户端同时重试把对方打挂（惊群效应）。
- **熔断 CircuitBreaker**：连续失败到阈值就「断开」，直接快速失败；过一段时间放一个探针请求探活，活了就闭合。这是微服务里老生常谈的套路，用来挡住不健康的下游。
- **缓存 SemanticCache**：把「消息 + 模型 + 工具」标准化成 key 存起来，一模一样的提问直接命中，省 token 又提速。

四者串起来：路由选人 → 先查缓存 → 没命中就带着重试和熔断去调模型 → 顺手记一笔账（Meter）。

### 三、关键实现点（代码党重点）

- **零依赖**：只用了标准库 `urllib` 发请求、`json` 解析，没有 `requests`、没有 `openai` SDK。好处是塞进任何环境都不用先 `pip install`，特别适合函数计算 / 沙箱。
- **Provider 抽象**：所有能力只依赖一个 `Provider.complete()` 接口。自带 `OpenAICompatibleProvider`（兼容 OpenAI 协议），还有 `ScriptedProvider`（按规则返回脚本结果）和 `EchoProvider`，让**整套逻辑不联网也能跑测试**。
- **Agent 循环**：一个极简 ReAct 思路——模型返回工具调用就本地执行、把结果塞回对话、再问一次，直到模型给出最终答案或到达 `max_iter`。工具 schema 直接用函数签名 + 类型注解自动推断，少写一堆 JSON Schema。
- **防坑细节**：缓存命中时返回的是**副本**而非原对象，避免「第一次调用也被标记成命中」的幽灵 bug；熔断的 lambda 包装用的是独立变量捕获，规避 Python 闭包延迟绑定导致的无限递归。

### 四、和同类方案比怎么样？

| 维度 | 裸调 SDK | 重型 Agent 框架 | Prism |
|------|---------|----------------|-------|
| 依赖 | 看 SDK | 重 | 零依赖 |
| 学习成本 | 低 | 高 | 低 |
| 弹性能力 | 自己写 | 有但耦合 | 可插拔、可单独用 |
| 适合场景 | Demo | 复杂产品 | 想快速获得「生产级外壳」 |

它不是要取代 Agent 框架，而是补上「框架之下、裸调之上」那一块弹性能力——你可以把它当积木，只拿 `CircuitBreaker` 或 `SemanticCache` 用。

### 五、怎么扩展？

- 想接别的模型？写个新 `Provider` 实现 `complete()` 就行。
- 想换缓存介质？把 `SemanticCache` 的 `get/put` 换成 Redis 实现。
- 想上监控？`Meter` 的 trace 直接喂 Prometheus。
- 想做「近似去重」？在 cache key 上接一个小向量模型，把「意思差不多」的提问也归并。

### 如何把本文扩展成一篇发布稿？

1. 开头加一段你**真实踩过的坑**（比如「上周模型抖动，接口 5 分钟全挂」），更有代入感。
2. 中间补一段**可运行的最小示例截图 / 终端录屏**（B 站 / 小红书尤其吃这个）。
3. 结尾抛一个问题引导评论，例如「你们生产里是怎么挡限流的？」。
4. 文末挂上仓库链接和 `#AI #Python #后端` 之类的话题标签。

---

<p align="center">Built with the Python standard library. No build step. No vendor lock-in.</p>
