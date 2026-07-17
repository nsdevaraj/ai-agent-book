"""
实验 10-3：书籍翻译 Agent —— 管理者模式（Orchestration）

本模块实现四种专职 Agent，以及两种运行方式：
  1) 管理者模式（orchestrate）：Manager 只保存任务/计划/调用记录/文件索引，
     不保存完整译文；各子 Agent 拥有独立、隔离的上下文。
  2) 单 Agent 模式（single_agent）：一个 Agent 在同一条不断增长的对话里
     依次读全书、逐章翻译，用于对照“上下文膨胀”与“术语漂移”。

核心验证点：
  - 记录每个 Agent / Manager 的上下文 token 消耗；
  - 证明管理者模式下 Manager 的上下文明显小于单 Agent 的累积上下文；
  - 证明共享术语表能让术语在各章保持一致。
"""

import os
import json

import tiktoken
from openai import OpenAI


# ----------------------------------------------------------------------------
# 配置：model / base_url 可通过环境变量覆盖，默认 gpt-4o-mini
# ----------------------------------------------------------------------------
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
BASE_URL = os.environ.get("OPENAI_BASE_URL")  # 可选，兼容自建/代理端点


def get_client() -> OpenAI:
    """创建 OpenAI 客户端，只使用 OPENAI_API_KEY。"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("未设置 OPENAI_API_KEY，请参考 env.example 配置。")
    kwargs = {"api_key": api_key}
    if BASE_URL:
        kwargs["base_url"] = BASE_URL
    return OpenAI(**kwargs)


# tiktoken 编码器：用于统计“未真正发给模型”的上下文（如 Manager 状态）token 数
try:
    _ENC = tiktoken.encoding_for_model(MODEL)
except Exception:
    _ENC = tiktoken.get_encoding("o200k_base")


def _slug(name: str) -> str:
    """把章节名转成干净的文件名前缀，如 'Chapter 1: ...' -> 'chapter1'。"""
    import re
    m = re.search(r"chapter\s*0*(\d+)", name, re.IGNORECASE)
    if m:
        return f"chapter{m.group(1)}"
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower() or "chapter"


def count_tokens(text: str) -> int:
    """统计一段文本的 token 数。"""
    return len(_ENC.encode(text or ""))


def count_messages_tokens(messages) -> int:
    """统计一组 chat messages 的 token 数（近似：内容 + 每条消息固定开销）。"""
    total = 0
    for m in messages:
        total += count_tokens(m.get("content", "")) + 4  # 每条消息约 4 token 结构开销
    return total


# ----------------------------------------------------------------------------
# Token 追踪器：记录每一次 LLM 调用的上下文规模，并按 Agent 聚合
# ----------------------------------------------------------------------------
class TokenTracker:
    """
    记录每个 Agent 每次调用的上下文 token 消耗。

    - prompt_tokens：本次调用发送给模型的“上下文”大小（真实 API usage）。
      这是衡量“上下文膨胀”的关键指标。
    - peak：某个 Agent 在其所有调用中，单次上下文的最大值（上下文峰值）。
    """

    def __init__(self):
        self.calls = []  # 每次调用一条记录

    def record(self, agent, prompt_tokens, completion_tokens, note=""):
        self.calls.append(
            {
                "agent": agent,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "note": note,
            }
        )

    def by_agent(self):
        """按 Agent 聚合：调用次数、输入/输出总量、上下文峰值。"""
        agg = {}
        for c in self.calls:
            a = agg.setdefault(
                c["agent"],
                {"calls": 0, "in": 0, "out": 0, "peak_context": 0},
            )
            a["calls"] += 1
            a["in"] += c["prompt_tokens"]
            a["out"] += c["completion_tokens"]
            a["peak_context"] = max(a["peak_context"], c["prompt_tokens"])
        return agg

    def total_tokens(self):
        return sum(c["prompt_tokens"] + c["completion_tokens"] for c in self.calls)


# ----------------------------------------------------------------------------
# LLM 调用封装：每次调用都带上 agent 名字，便于按 Agent 记账
# ----------------------------------------------------------------------------
def llm_chat(client, tracker, agent, messages, json_mode=False, note=""):
    """
    发起一次 chat completion，并把真实 token usage 记入 tracker。

    注意：messages 是本次调用的“独立上下文”。子 Agent 每次都从零构造 messages，
    因此各 Agent 的上下文天然隔离，互不污染。
    """
    kwargs = {"model": MODEL, "messages": messages, "temperature": 0.2}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)
    usage = resp.usage
    tracker.record(agent, usage.prompt_tokens, usage.completion_tokens, note)
    return resp.choices[0].message.content


# ============================================================================
# 四种专职 Agent
# ============================================================================

# 编辑部指定术语（house style）：Manager 会把这些译法强制写入共享术语表，
# 让所有 Translation Agent 全书统一采用。单 Agent 看不到术语表，无法贯彻。
EDITORIAL_MANDATE = {
    "token": "词元",
    "prompt": "提示词",
    "latency": "时延",
    "embedding": "嵌入向量",
}


TRANSLATION_GUIDE = (
    "翻译指南：面向中文技术读者，语言流畅自然；保留 Markdown 结构；"
    "代码块内的代码原样保留、不翻译（可保留英文注释）；"
    "术语表中出现的术语必须严格使用规定译法；遇到术语表之外的新术语，"
    "先给出你推断的译法，并在其后紧跟标记 [待审] 提示人工复核。"
)


def glossary_agent(client, tracker, book_text):
    """
    Glossary Agent：读全书内容，识别反复出现的专业术语，
    输出结构化术语对照表（JSON）。独立上下文，产出后即可释放。
    """
    system = (
        "你是术语抽取专家。阅读整本技术书，找出反复出现的专业术语，"
        "为每个术语给出统一的中文译法。只输出 JSON。"
    )
    user = (
        "请阅读下面全书内容，抽取 6-10 个反复出现的核心专业术语，"
        "输出 JSON，格式为："
        '{"glossary": [{"en": "英文术语", "zh": "中文译法", '
        '"pos": "词性", "context": "该术语在书中的语境说明"}]}。\n\n'
        "全书内容如下：\n\n" + book_text
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    content = llm_chat(
        client, tracker, "Glossary", messages, json_mode=True, note="抽取术语表"
    )
    data = json.loads(content)
    return data.get("glossary", [])


def translation_agent(client, tracker, chapter_text, glossary, chapter_name, feedback=None):
    """
    Translation Agent：接收「当前章节 + 术语表 + 翻译指南」，翻成流畅中文。
    每个实例都是独立上下文（只看到自己这一章 + 术语表，不看到别的章节译文）。

    feedback：可选，Manager 依据审校报告发回的针对本章的修订意见。
    """
    glossary_lines = "\n".join(
        f'- {g["en"]} → {g["zh"]}（{g.get("pos","")}）' for g in glossary
    )
    system = "你是专业技术翻译。把英文章节翻译为流畅、准确的中文。"
    user = (
        f"{TRANSLATION_GUIDE}\n\n"
        f"【术语表（必须严格遵守）】\n{glossary_lines}\n\n"
    )
    if feedback:
        user += f"【本章修订意见（请据此修改）】\n{feedback}\n\n"
    user += (
        f"【待翻译章节：{chapter_name}】\n{chapter_text}\n\n"
        "请直接输出该章节的中文译文（Markdown），不要额外解释。"
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    note = f"翻译 {chapter_name}" + ("（修订）" if feedback else "")
    return llm_chat(client, tracker, "Translation", messages, note=note)


def proofreading_agent(client, tracker, translations, glossary):
    """
    Proofreading Agent：接收所有译文 + 术语表，做一致性检查
    （术语是否统一、前后是否矛盾、是否流畅），输出结构化审校报告（JSON）。

    translations：{chapter_name: 译文文本}
    """
    glossary_lines = "\n".join(f'- {g["en"]} → {g["zh"]}' for g in glossary)
    joined = "\n\n".join(
        f"===== {name} =====\n{text}" for name, text in translations.items()
    )
    system = (
        "你是资深审校。检查多章译文的术语一致性、前后一致性与流畅性。"
        "只输出 JSON。"
    )
    user = (
        f"【术语表】\n{glossary_lines}\n\n"
        f"【全部译文】\n{joined}\n\n"
        "请输出 JSON："
        '{"issues": [{"chapter": "章节名", "type": "术语不一致/前后矛盾/流畅性", '
        '"detail": "问题描述"}], "chapters_need_revision": ["需要修订的章节名"], '
        '"summary": "总体评价"}'
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    content = llm_chat(
        client, tracker, "Proofreading", messages, json_mode=True, note="一致性审校"
    )
    return json.loads(content)


def manager_decision(client, tracker, task, file_index, report):
    """
    Manager Agent 的一次真实 LLM 决策调用。

    关键点：Manager 只把「任务 + 文件索引 + 审校报告摘要」这类很小的上下文
    发给模型，用来决定「哪些章节需要发回 Translation Agent 修订」。
    它从不把完整译文放进自己的上下文 —— 这正是控制 Manager 上下文膨胀的做法。
    """
    system = "你是翻译项目的管理者，只做调度决策，输出 JSON。"
    user = (
        f"任务：{task}\n"
        f"文件索引（只存路径，不存正文）：{json.dumps(file_index, ensure_ascii=False)}\n"
        f"审校报告摘要：{json.dumps(report, ensure_ascii=False)}\n\n"
        "根据审校报告，决定需要修订的章节。输出 JSON："
        '{"revise": ["章节名", ...], "reason": "简述"}'
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    content = llm_chat(
        client, tracker, "Manager", messages, json_mode=True, note="调度决策"
    )
    return json.loads(content)


# ============================================================================
# 运行方式一：管理者模式（Orchestration）
# ============================================================================
def run_orchestration(chapters, out_dir):
    """
    chapters：{chapter_name: 英文原文} 的有序字典
    out_dir：产物目录（术语表、各章译文、审校报告都写到这里）

    返回：metrics 字典，含 tracker、manager 上下文峰值、译文映射等。
    """
    os.makedirs(out_dir, exist_ok=True)
    client = get_client()
    tracker = TokenTracker()

    # ---- Manager 的上下文：只保存这些“轻量”信息，绝不含完整译文 ----
    manager_context = {
        "task": "把一本英文技术小书翻译成流畅中文，保证术语全书一致。",
        "guide": TRANSLATION_GUIDE,
        "plan": [
            "1. 调用 Glossary Agent 生成术语表并落盘",
            "2. 逐章调用 Translation Agent（各自独立上下文，共享术语表文件）",
            "3. 调用 Proofreading Agent 做一致性审校并落盘报告",
            "4. 依据报告决定是否发回个别章节修订",
        ],
        "call_log": [],       # 各 Agent 调用记录（只记摘要，不记正文）
        "file_index": {},     # 文件索引：只存路径
        "progress": {},       # 进度状态
    }
    manager_peak = 0  # Manager 上下文（其状态序列化后的）token 峰值

    def snapshot_manager():
        nonlocal manager_peak
        size = count_tokens(json.dumps(manager_context, ensure_ascii=False))
        manager_peak = max(manager_peak, size)
        return size

    def log_call(agent, note, out_file, prompt_tokens, completion_tokens):
        # Manager 只记录“谁做了什么、产物在哪、花了多少 token”，不记录正文
        manager_context["call_log"].append(
            {
                "agent": agent,
                "note": note,
                "output": out_file,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        )
        snapshot_manager()

    snapshot_manager()

    # ---- 步骤 1：Glossary Agent（独立上下文，读全书；产出后释放）----
    book_text = "\n\n".join(f"# {n}\n{t}" for n, t in chapters.items())
    glossary = glossary_agent(client, tracker, book_text)
    # Manager 把“编辑部指定术语”强制写入术语表（覆盖或新增），作为全书统一契约。
    for g in glossary:
        en = g["en"].strip().lower()
        if en in EDITORIAL_MANDATE:
            g["zh"] = EDITORIAL_MANDATE[en]
    present = {g["en"].strip().lower() for g in glossary}
    for en, zh in EDITORIAL_MANDATE.items():
        if en not in present:
            glossary.append({"en": en, "zh": zh, "pos": "名词", "context": "编辑部指定术语"})
    glossary_path = os.path.join(out_dir, "glossary.json")
    with open(glossary_path, "w", encoding="utf-8") as f:
        json.dump(glossary, f, ensure_ascii=False, indent=2)
    # Manager 只在文件索引里记路径；术语表正文留在文件系统，不进 Manager 上下文
    manager_context["file_index"]["glossary"] = glossary_path
    last = tracker.calls[-1]
    log_call("Glossary", f"抽取 {len(glossary)} 个术语", glossary_path,
             last["prompt_tokens"], last["completion_tokens"])

    # ---- 步骤 2：逐章 Translation Agent（每章一个独立上下文实例）----
    translations = {}
    for name, text in chapters.items():
        zh = translation_agent(client, tracker, text, glossary, name)
        # 文件名如 chapter1_zh.md
        base = _slug(name)
        out_file = os.path.join(out_dir, f"{base}_zh.md")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(zh)
        translations[name] = zh
        manager_context["file_index"][name] = out_file
        manager_context["progress"][name] = "translated"
        last = tracker.calls[-1]
        log_call("Translation", f"翻译 {name}", out_file,
                 last["prompt_tokens"], last["completion_tokens"])

    # ---- 步骤 3：Proofreading Agent（读所有译文 + 术语表，独立上下文）----
    report = proofreading_agent(client, tracker, translations, glossary)
    report_path = os.path.join(out_dir, "proofreading_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    manager_context["file_index"]["report"] = report_path
    last = tracker.calls[-1]
    log_call("Proofreading", "一致性审校", report_path,
             last["prompt_tokens"], last["completion_tokens"])

    # ---- 步骤 4：Manager 决策 + 至多一轮修订 ----
    # Manager 只把“文件索引 + 报告摘要”这类小上下文发给模型做决策
    report_summary = {
        "chapters_need_revision": report.get("chapters_need_revision", []),
        "issues": report.get("issues", [])[:5],
        "summary": report.get("summary", ""),
    }
    manager_context["progress"]["proofread"] = "done"
    snapshot_manager()

    decision = manager_decision(
        client, tracker, manager_context["task"],
        manager_context["file_index"], report_summary
    )
    revise = decision.get("revise", [])

    for name in revise:
        if name not in chapters:
            continue
        # 找到该章节的修订意见
        fb = "; ".join(
            i.get("detail", "") for i in report.get("issues", [])
            if i.get("chapter") == name
        ) or "请根据术语表统一术语并提升流畅性。"
        zh = translation_agent(client, tracker, chapters[name], glossary, name, feedback=fb)
        base = _slug(name)
        out_file = os.path.join(out_dir, f"{base}_zh.md")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(zh)
        translations[name] = zh
        manager_context["progress"][name] = "revised"
        last = tracker.calls[-1]
        log_call("Translation", f"修订 {name}", out_file,
                 last["prompt_tokens"], last["completion_tokens"])

    snapshot_manager()

    return {
        "mode": "orchestration",
        "tracker": tracker,
        "manager_context_peak": manager_peak,
        "manager_context_final": manager_context,
        "glossary": glossary,
        "translations": translations,
        "report": report,
        "out_dir": out_dir,
    }


# ============================================================================
# 运行方式二：单 Agent 模式（对照组）
# ============================================================================
def run_single_agent(chapters, out_dir):
    """
    朴素基线：一个 Agent 在同一条不断增长的对话里，先粗读全书，
    再逐章翻译。没有独立的术语表工具来“钉死”术语，且上下文随章节累积。

    这一模式用于暴露两个问题：
      - 上下文膨胀：单条对话的上下文峰值 = 累积到最后一章时的全部内容；
      - 术语漂移：缺少共享术语表约束，同一术语在不同章可能译法不一致。
    """
    os.makedirs(out_dir, exist_ok=True)
    client = get_client()
    tracker = TokenTracker()

    system = (
        "你是专业技术翻译。我会逐章给你一本英文技术书，请把每一章翻译成"
        "流畅、准确的中文。保留 Markdown 结构；代码块内的代码原样保留、不翻译。"
    )
    # 单 Agent 的“主上下文”：一条持续增长的对话
    messages = [{"role": "system", "content": system}]

    translations = {}
    for name, text in chapters.items():
        messages.append(
            {
                "role": "user",
                "content": f"请翻译下面这一章，直接输出中文译文：\n\n# {name}\n{text}",
            }
        )
        content = llm_chat(
            client, tracker, "SingleAgent", messages, note=f"翻译 {name}"
        )
        # 译文继续留在对话里 —— 这正是上下文膨胀的来源
        messages.append({"role": "assistant", "content": content})
        translations[name] = content
        base = _slug(name)
        out_file = os.path.join(out_dir, f"{base}_zh.md")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(content)

    return {
        "mode": "single_agent",
        "tracker": tracker,
        # 单 Agent 的“主上下文峰值”= 其所有调用中最大的一次 prompt_tokens
        "main_context_peak": tracker.by_agent()["SingleAgent"]["peak_context"],
        "translations": translations,
        "out_dir": out_dir,
    }
