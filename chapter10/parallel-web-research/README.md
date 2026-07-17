# 实验 10-6 · 同时从多个网站搜集信息的 Agent（★★）

《深入理解 AI Agent》配套实验。演示**多个同构 Agent 的并行搜索 + 中心协调**：
主协调器同时启动 N 个子 Agent，每个子 Agent 访问一个"网站/来源"找答案；
一旦某个子 Agent 命中目标，其余立即优雅停止。

书中的原型是"10 个并行的 Computer Use Agent 同时访问不同网站找信息"。为便于
自动验证，本实验**不启动真实浏览器**，而是用一批**可控的模拟信息源**代替；把重点
完整放在协调机制上——**消息总线、并行派发、实时监控、级联终止、竞态处理均为真实实现**。

## 目录结构

| 文件 | 作用 |
| --- | --- |
| `message_bus.py` | 进程内异步消息总线（Redis Pub/Sub 风格），带 `Envelope` 信封与订阅机制 |
| `sources.py` | 模拟的 10 个"网站/来源"，各有不同延迟；可控的关键词命中判断 |
| `llm.py` | 可选的 LLM 判断层（默认离线关键词判断，配了 key 则用真实大模型） |
| `agents.py` | 主协调器 `Coordinator` 与子 Agent `WorkerAgent`（核心协调逻辑） |
| `demo.py` | 一条命令的演示入口，末尾带断言式自检 |

## 架构与机制

```
                         ┌────────────────────────────┐
                         │   Coordinator（主协调器）    │
                         │  · 并行派发 task_assigned    │
                         │  · 维护任务状态表(状态机)     │
                         │  · 首个命中→加锁结算(幂等)    │
                         │  · 广播一轮 terminate        │
                         └───────────┬────────────────┘
                                     │
                    ┌────────────────┴─────── MessageBus（异步消息总线）───────┐
                    │  Envelope{ sender_id, target, type, payload, seq, ts }    │
                    │  type: task_assigned/status_update/result/terminate/ack   │
                    └──┬─────────┬─────────┬─────────┬──────────────┬──────────┘
                       │         │         │         │              │
                    ┌──▼──┐  ┌──▼──┐  ┌──▼──┐  ┌──▼──┐   ...   ┌──▼──┐
                    │W-00 │  │W-01 │  │W-02 │  │W-03 │         │W-09 │  子 Agent
                    │网站A│  │网站B│  │网站C│  │网站D│         │网站J│  （同构·并行）
                    └─────┘  └─────┘  └─────┘  └─────┘         └─────┘
```

对应书中强调的五个机制：

1. **消息总线（Message Bus）**：所有通信都是发布到总线的**带信封消息**，按 `type`
   订阅。日志中每条 `BUS ...` 行就是一次发布/投递（Redis Pub/Sub 语义的进程内实现）。
2. **并行派发**：`Coordinator` 同时给 10 个子 Agent 发 `task_assigned` 并 `asyncio.create_task` 并发执行。
3. **实时监控（push 范式）**：子 Agent 执行中主动 `status_update` 上报进度，
   主 Agent 维护**任务状态表**并在状态机跳变时实时刷新打印。
   状态机：`已提交 → 执行中 →（需要输入）→ 已完成 / 失败 / 已终止`。
4. **级联终止**：某子 Agent 命中后，主 Agent **广播 `terminate`**；其余子 Agent 在
   循环的**安全检查点**发现信号后回 `ack` 并优雅退出（状态置为"已终止"）。
5. **竞态处理**：多个子 Agent 可能几乎同时命中，主 Agent 用 `asyncio.Lock` +
   幂等标志 `_settled` 保证**只结算一次、只广播一轮终止**；迟到的命中被记录并忽略。

> 为让"竞态""级联终止"可复现，各来源被赋予不同的模拟延迟，其中 `geo-journal` 与
> `forum-qa` 两个正确源被设成**相同延迟**，从而稳定地在同一时刻命中、触发竞态。

## 运行

```bash
cd chapter10/parallel-web-research
pip install -r requirements.txt   # 仅离线演示的话可跳过，纯标准库即可运行
python demo.py
```

默认走**离线关键词判断**（无需联网、结果可复现）。若要让子 Agent 用真实 LLM 判断：

```bash
cp env.example .env
# 在 .env 填入 OPENAI_API_KEY（也支持 Moonshot / 火山方舟 ARK 的 OpenAI 兼容网关）
python demo.py
```

可用 key：`OPENAI_API_KEY` / `MOONSHOT_API_KEY` / `ARK_API_KEY`（填到 `OPENAI_API_KEY`
并按需设置 `OPENAI_BASE_URL`、`OPENAI_MODEL`）。不影响协调机制，仅改变"是否命中"的判断。

## 演示说明什么（真实运行输出关键片段）

**(a) 消息总线的发布/订阅在工作**——每条带信封的消息都打印出来：

```
BUS [t=  0.00s #3  ] coordinator -> worker-02   | task_assigned  | {"question": "...", "source": "geo-journal"}
BUS [t=  0.00s #13 ]   worker-02 -> coordinator | status_update  | {"state": "执行中", ...}
```

**(b) N 个子 Agent 并行执行 + 主 Agent 实时刷新状态表**：

```
── 任务状态表（worker-02 -> 执行中） ──
   worker-00  源=baike-wiki   状态=执行中   | 开始抓取来源
   worker-02  源=geo-journal  状态=执行中   | 开始抓取来源
   ...
```

**(c) 级联终止**——命中后广播 terminate，其余子 Agent ack 并优雅退出：

```
BUS [t=0.60s #41 ] coordinator -> ALL         | terminate | {"reason":"answer_found","winner":"worker-02"}
BUS [t=0.67s #43 ]   worker-09 -> coordinator | ack       | {"acked":"terminate","source":"map-service"}
[ack] worker-09 已确认终止（1 个已 ack）
...最终 8 个未命中的 Worker 全部状态=已终止
```

**(d) 竞态：即使几乎同时命中，也只结算一次、只广播一轮终止**：

```
BUS [t=0.60s #37 ]   worker-02 -> coordinator | result | {"found":true, "answer":"...珠穆朗玛峰...8848 米..."}
BUS [t=0.60s #38 ]   worker-04 -> coordinator | result | {"found":true, "answer":"...珠穆朗玛峰...8848.86 米..."}
[结算] 首个命中来自 worker-02 —— 加锁结算，广播一轮 terminate。
[竞态] worker-04 也命中，但已由 worker-02 结算 —— 忽略此次命中，不重复广播终止。
```

`demo.py` 末尾有**断言式自检**：`terminate 广播轮数 == 1`、`只结算一次 == True`、
`winner 非空`。跑通即证明机制正确：

```
4) terminate 广播轮数：1（应为 1，证明只广播一轮）
   迟到/并发的重复命中被忽略：['worker-04']
[自检通过] 单次结算 + 单轮终止广播 + 级联 ack 均符合预期。
```

## 注意事项

- 这里用**进程内 async 消息总线**模拟 Redis Pub/Sub，无需真装 Redis；语义（信封、
  按类型订阅、点对点/广播投递）一致，便于单机复现与自动验证。
- 不启动真实浏览器：来源是可控的模拟数据 + 延迟。若要接真实 Computer Use，只需把
  `WorkerAgent.run()` 里的"抓取一步 + 判断"换成真实浏览器操作，协调层无需改动。
- 竞态之所以稳定复现，是因为把两个正确源的延迟设成相同；真实环境里竞态是偶发的，
  但加锁 + 幂等的结算逻辑对偶发竞态同样成立。
- 子 Agent 在循环里**定期检查终止信号**（每步抓取前后），因此终止是"安全点响应"而非
  强杀，能保证资源被正常收尾。
