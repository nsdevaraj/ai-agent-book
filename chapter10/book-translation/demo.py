"""
实验 10-3 一键演示。

  python demo.py

流程：
  1) 读入 sample_book/ 下的 3-4 个英文短章节；
  2) 运行【管理者模式】：Glossary / Translation / Proofreading / Manager 四种 Agent 协作；
  3) 运行【单 Agent 模式】作为对照；
  4) 打印对比表：每个 Agent 的上下文 token 消耗、Manager/主上下文峰值、术语一致性。

结论要点：
  - 管理者模式下 Manager 的上下文明显小于单 Agent 的累积上下文（控制上下文膨胀）；
  - 共享术语表让术语在各章保持一致。
"""

import os
import glob

from dotenv import load_dotenv

import agents
import consistency

load_dotenv()

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(HERE, "sample_book")
OUT_DIR = os.path.join(HERE, "output")


def load_chapters():
    """按文件名顺序读入 sample_book/*.md，返回 {章节名: 原文}。"""
    files = sorted(glob.glob(os.path.join(SAMPLE_DIR, "*.md")))
    chapters = {}
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        # 用文件的一级标题作为章节名，回退到文件名
        name = os.path.splitext(os.path.basename(path))[0]
        for line in text.splitlines():
            if line.startswith("# "):
                name = line[2:].strip()
                break
        chapters[name] = text
    return chapters


def hr(title=""):
    print("\n" + "=" * 72)
    if title:
        print(title)
        print("=" * 72)


def print_agent_table(tracker, title):
    hr(title)
    agg = tracker.by_agent()
    print(f"{'Agent':<14}{'调用次数':>8}{'输入tok':>12}{'输出tok':>12}{'上下文峰值':>12}")
    print("-" * 72)
    for name, a in agg.items():
        print(f"{name:<14}{a['calls']:>8}{a['in']:>12}{a['out']:>12}{a['peak_context']:>12}")
    print("-" * 72)
    print(f"{'合计':<14}{'':>8}{'':>12}{'':>12}  总 token：{tracker.total_tokens()}")


def print_consistency(analysis, label):
    print(f"\n[{label}] 术语一致性：{analysis['consistent_terms']}/{analysis['total_terms']} "
          f"个术语全书统一（{analysis['rate']*100:.0f}%）")
    for r in analysis["results"]:
        flag = "一致" if r["consistent"] else "不一致 <==="
        used = " / ".join(f"{v}({len(chs)}章)" for v, chs in r["by_variant"].items())
        print(f"  - {r['en']:<12} 实际用到：{used}  [{flag}]")


def main():
    chapters = load_chapters()
    print(f"载入 {len(chapters)} 个章节：{list(chapters.keys())}")

    # ---------------- 管理者模式 ----------------
    orch = agents.run_orchestration(chapters, os.path.join(OUT_DIR, "orchestration"))
    print_agent_table(orch["tracker"], "【管理者模式】各 Agent 上下文 token 消耗")
    print(f"\nManager 上下文峰值（只存任务/计划/调用记录/文件索引）：{orch['manager_context_peak']} tokens")
    print(f"术语表（共享文件，各 Translation Agent 引用同一份）：")
    for g in orch["glossary"]:
        print(f"    {g['en']} → {g['zh']}（{g.get('pos','')}）")
    print(f"审校报告 summary：{orch['report'].get('summary','')[:120]}")

    # ---------------- 单 Agent 模式 ----------------
    single = agents.run_single_agent(chapters, os.path.join(OUT_DIR, "single_agent"))
    print_agent_table(single["tracker"], "【单 Agent 模式】主上下文 token 消耗")

    # ---------------- 术语一致性对比 ----------------
    hr("术语一致性对比（确定性字符串匹配，非模型打分）")
    orch_cons = consistency.analyze(orch["translations"])
    single_cons = consistency.analyze(single["translations"])
    print_consistency(orch_cons, "管理者模式")
    print_consistency(single_cons, "单 Agent 模式")

    # ---------------- 术语表遵从率对比（核心证据）----------------
    hr("术语表遵从率对比：编辑部指定术语能否贯彻全书")
    orch_adh = consistency.check_adherence(orch["translations"])
    single_adh = consistency.check_adherence(single["translations"])
    print("（管理者模式把指定术语写入共享术语表并强制下发；单 Agent 看不到术语表）\n")
    print(f"{'指定术语':<14}{'规定译法':<10}{'默认译法':<10}"
          f"{'管理者(遵从/出现)':>18}{'单Agent(遵从/出现)':>20}")
    print("-" * 78)
    o_map = {r["en"]: r for r in orch_adh["rows"]}
    s_map = {r["en"]: r for r in single_adh["rows"]}
    for r in orch_adh["rows"]:
        s = s_map.get(r["en"], {"adhered": 0, "total": 0})
        o_cell = f"{r['adhered']}/{r['total']}"
        s_cell = f"{s['adhered']}/{s['total']}"
        print(f"{r['en']:<14}{r['mandated']:<10}{r['default']:<10}"
              f"{o_cell:>18}{s_cell:>20}")
    print("-" * 78)
    print(f"术语表遵从率：管理者模式 {orch_adh['rate']*100:.0f}%  vs  "
          f"单 Agent {single_adh['rate']*100:.0f}%")

    # ---------------- 核心对比表 ----------------
    hr("核心对比表：管理者模式 vs 单 Agent 模式")
    o_tr, s_tr = orch["tracker"], single["tracker"]
    o_mgr_peak = orch["manager_context_peak"]
    # 管理者模式里，若把 Manager 当作 LLM Agent，它也有一次决策调用的上下文峰值
    o_mgr_llm_peak = o_tr.by_agent().get("Manager", {}).get("peak_context", 0)
    s_main_peak = single["main_context_peak"]

    rows = [
        ("主/Manager 上下文峰值(tokens)", o_mgr_peak, s_main_peak),
        ("Manager LLM 决策调用上下文(tokens)", o_mgr_llm_peak, "—"),
        ("全流程总 token 消耗", o_tr.total_tokens(), s_tr.total_tokens()),
        ("术语内部一致率", f"{orch_cons['rate']*100:.0f}%", f"{single_cons['rate']*100:.0f}%"),
        ("指定术语遵从率", f"{orch_adh['rate']*100:.0f}%", f"{single_adh['rate']*100:.0f}%"),
        ("参与 Agent 种类数", len(o_tr.by_agent()), 1),
    ]
    print(f"{'指标':<32}{'管理者模式':>16}{'单 Agent':>16}")
    print("-" * 72)
    for label, a, b in rows:
        print(f"{label:<32}{str(a):>16}{str(b):>16}")
    print("-" * 72)

    if isinstance(s_main_peak, int) and o_mgr_peak and s_main_peak:
        ratio = s_main_peak / o_mgr_peak
        print(f"\n结论：单 Agent 主上下文峰值是管理者模式 Manager 上下文的 "
              f"{ratio:.1f} 倍。")
        print("Manager 只保存任务/计划/调用记录/文件索引，完整译文全部落盘到文件系统，")
        print("因此无论书有多长，Manager 上下文都基本恒定 —— 这就是控制上下文膨胀的关键。")
    print(f"\n产物目录：{OUT_DIR}")


if __name__ == "__main__":
    main()
