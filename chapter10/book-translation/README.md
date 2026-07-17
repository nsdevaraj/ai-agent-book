# 实验 10-3：书籍翻译 Agent —— 管理者模式（Orchestration）

配套代码，演示如何用**管理者模式**把长文档翻译拆给多个专职 Agent。核心是
**上下文隔离**与**控制 Manager 上下文膨胀**：Manager 只保存任务、计划、各
Agent 调用记录和文件索引，**完整译文全部落盘到文件系统**，因此无论书有多长，
Manager 的上下文都基本恒定。

## 目的

对比「单 Agent 一条对话翻完整本书」与「管理者模式多 Agent 协作」两种方案，用
**真实 token 数**说明后者如何控制主/Manager 上下文膨胀，并用**共享术语表**保证
全书术语一致。

## 架构：四种 Agent

| Agent | 输入（独立上下文） | 产出 | 上下文特点 |
| --- | --- | --- | --- |
| **Glossary Agent** | 全书内容 | 结构化术语表 `glossary.json` | 读全书，产出后即释放 |
| **Translation Agent** | 当前章节 + 术语表 + 翻译指南 | `chapterN_zh.md` | 每章一个独立实例，只看到自己这一章 |
| **Proofreading Agent** | 所有译文 + 术语表 | 审校报告 `proofreading_report.json` | 做一致性 / 流畅性检查 |
| **Manager Agent** | 任务 + 文件索引 + 报告摘要 | 调度决策（是否发回修订） | **只存元信息，不存正文** |

数据流：Manager 调度 Glossary → 逐章 Translation（共享同一份术语表文件）→
Proofreading → Manager 依据报告决定是否把个别章节发回 Translation 修订。译文与
术语表都通过**文件系统**传递，Manager 只在上下文里保存文件路径。

关键设计：Manager 把「编辑部指定术语」（house style，如 token→词元、
prompt→提示词、latency→时延）强制写入共享术语表，下发给每个 Translation Agent，
从而把指定译法贯彻到全书。单 Agent 看不到术语表，只能用自己的默认译法。

## 目录

```
book-translation/
├── agents.py          # 四种 Agent + 两种运行方式 + token 追踪
├── consistency.py     # 术语一致性 / 术语表遵从率（确定性字符串匹配）
├── demo.py            # 一键演示：跑管理者模式 + 单 Agent 对照，打印对比表
├── sample_book/       # 自带英文技术小书（4 个短章节，含术语与代码）
│   ├── chapter1.md ... chapter4.md
├── output/            # 运行时生成：术语表 / 各章译文 / 审校报告（已 gitignore）
├── requirements.txt
└── env.example
```

## 运行

```bash
pip install -r requirements.txt
cp env.example .env      # 填入 OPENAI_API_KEY
python demo.py
```

- 只使用 `OPENAI_API_KEY`。模型默认 `gpt-4o-mini`（成本低），可用 `OPENAI_MODEL`
  覆盖；如需自建/代理端点，设 `OPENAI_BASE_URL`。
- 任务规模刻意很小（4 个短章节），一次运行成本约几百分之一美元。

## token 统计口径

- 子 Agent / 单 Agent 的输入、输出 token 取 OpenAI 返回的**真实 usage**。
- 「上下文峰值」= 某 Agent 所有调用中，单次输入上下文（prompt tokens）的最大值，
  用来衡量上下文膨胀。
- Manager 上下文峰值：Manager 状态（任务/计划/调用记录/文件索引）序列化后用
  `tiktoken` 统计的 token 数峰值 —— 它从不包含完整译文。

## 结论（真实运行结果，gpt-4o-mini，4 章）

| 指标 | 管理者模式 | 单 Agent |
| --- | --- | --- |
| 主/Manager 上下文峰值 (tokens) | **926** | **2199** |
| Manager LLM 决策调用上下文 (tokens) | 374 | — |
| 全流程总 token | 7170 | 6399 |
| 术语内部一致率 | 100% | 100% |
| 指定术语遵从率 | **100%** | **0%** |
| 参与 Agent 种类数 | 4 | 1 |

1. **控制上下文膨胀**：单 Agent 的主上下文随章节累积，峰值达 2199 tokens；管理者
   模式下 Manager 上下文峰值仅 926 tokens（约 2.4 倍差距）。更重要的是，Manager
   上下文与书的长度**基本无关**（只加一行调用记录/文件索引），而单 Agent 的累积
   上下文会随章节线性增长——书越长，差距越大。子 Agent 的上下文各自隔离、互不污染
   （每个 Translation 实例峰值仅约 560 tokens）。
2. **术语一致性**：管理者模式把编辑部指定术语写入共享术语表并强制下发，4 个指定
   术语在全书的遵从率 **100%**；单 Agent 看不到术语表，遵从率 **0%**（全书都用它
   自己的默认译法，如 token 译成「标记」而非规定的「词元」）。对真正的长文档，单
   Agent 还会因早期章节被挤出上下文而出现跨章漂移，管理者模式的共享术语表天然免疫。
3. **代价**：管理者模式多花了少量 token（额外的术语表抽取、审校、调度调用），换来
   的是**主上下文可控**与**术语可强制统一**——这正是长文档翻译真正需要的性质。

> 说明：术语一致性用确定性字符串匹配统计（见 `consistency.py`），不是让模型自评。
> 具体数字每次运行会有小幅波动，但上述量级与结论稳定复现。
