"""
实验 10-6 演示入口：同时从多个网站搜集信息的 Agent
=================================================

一条命令即可运行：

    python demo.py

演示内容（对应书中强调的机制）：
  (a) 消息总线的发布/订阅：日志里可见带信封的消息流（BUS 前缀）；
  (b) N 个子 Agent 并行执行，主协调器实时刷新任务状态表；
  (c) 某子 Agent 命中后触发级联终止，其余 Agent 收到 terminate 并优雅退出（ack）；
  (d) 多个子 Agent 几乎同时命中时，只结算一次、只广播一轮终止（幂等 + 加锁）。

默认使用离线的关键词判断，保证结果可复现；
若配置了 OPENAI_API_KEY 且未设 USE_LLM=0，子 Agent 会改用真实 LLM 做判断。
"""

from __future__ import annotations

import asyncio
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # noqa: BLE001 —— 没装 python-dotenv 也能跑
    pass

from agents import Coordinator, WorkerAgent
from message_bus import MessageBus
from sources import DEMO_SOURCES, QUESTION


async def main():
    print("=" * 78)
    print("实验 10-6 · 同时从多个网站搜集信息的 Agent（并行搜索 + 中心协调）")
    print("=" * 78)
    print(f"任务问题：{QUESTION}")
    print(f"并行来源数：{len(DEMO_SOURCES)} 个模拟'网站'")
    print("说明：geo-journal 与 forum-qa 两个源都含正确答案且延迟接近，用于演示竞态。")
    print("-" * 78)

    bus = MessageBus(verbose=True)
    coordinator = Coordinator(bus, QUESTION)

    # 并行装配 N 个同构子 Agent，每个绑定一个来源
    for i, src in enumerate(DEMO_SOURCES):
        w = WorkerAgent(f"worker-{i:02d}", src, bus, QUESTION)
        coordinator.add_worker(w)

    result = await coordinator.run()

    print("=" * 78)
    print("演示结论（自动校验）")
    print("=" * 78)
    total_msgs = len(bus.history)
    print(f"1) 消息总线共传递 {total_msgs} 条带信封消息（发布/订阅正常工作）。")
    print(f"2) {len(coordinator.workers)} 个子 Agent 并行执行，状态表全程实时刷新。")
    print(f"3) 首个命中并结算的 Worker：{result['winner']}")
    print(f"   答案：{result['answer']}")
    print(f"   收到 terminate 并 ack 的 Worker：{result['acks']}")
    print(f"4) terminate 广播轮数：{result['terminate_broadcasts']}（应为 1，证明只广播一轮）")
    print(f"   迟到/并发的重复命中被忽略：{result['duplicate_hits'] or '无（本次无并发迟到命中）'}")
    print(f"   是否只结算一次：{result['settled_once']}")

    # —— 断言式自检：跑通即证明机制正确 ——
    assert result["winner"] is not None, "应至少有一个 Worker 命中"
    assert result["terminate_broadcasts"] == 1, "级联终止只能广播一轮"
    assert result["settled_once"] is True, "必须完成且只结算一次"
    print("\n[自检通过] 单次结算 + 单轮终止广播 + 级联 ack 均符合预期。")


if __name__ == "__main__":
    asyncio.run(main())
