"""V1.2 Emotion detection and psychological support module.

Provides rule-based emotion/psychological-keyword detection and response strategies.
Designed to handle the emotional side of diet management — the hardest part.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EmotionResult:
    tone: str                    # positive / negative / anxious / guilty / neutral / illness
    keywords: list[str] = field(default_factory=list)
    response: str = ""
    should_block_meal_parsing: bool = False  # when True, skip diet parsing entirely


# ── emotion patterns ─────────────────────────────────────────────────────────
# Each entry: (keywords, tone, response_template, block_meal_parsing)

EMOTION_PATTERNS: list[tuple[list[str], str, str, bool]] = [
    # —— guilt / binge anxiety ——
    (
        ["暴食", "吃太多", "吃多了", "控制不住", "毁了", "完蛋了", "白费了", "全毁了"],
        "guilty",
        (
            '一餐不会改变整体方向。你已经记录了它，这是负责任的一步。\n'
            '需要我帮你回顾本周数据客观看看吗？发送「本周」——我来帮你客观分析。'
        ),
        False,
    ),
    (
        ["忍不住", "后悔", "罪恶", "罪恶感", "不该吃", "偷吃", "偷吃了"],
        "guilty",
        (
            "食物没有'好'和'坏'之分，记录它，然后下一餐继续按计划来。\n"
            "偶尔的偏离不会影响长期趋势。"
        ),
        False,
    ),
    # —— discouragement / plateau ——
    (
        [
            "没效果",
            "平台期",
            "平台",
            "想放弃",
            "太慢了",
            "看不到变化",
            "没变化",
            "没瘦",
            "没减下来",
        ],
        "anxious",
        (
            '我理解这种感觉。体重变化本来就不是线性的——水分、睡眠、压力都会影响短期数据。\n'
            '发送「本周」让我帮你看看客观趋势？有时数据会告诉我们不一样的故事。'
        ),
        False,
    ),
    (
        ["放弃", "不想记了", "不想继续", "太累了"],
        "negative",
        (
            "没关系，暂停一段时间完全可以。饮食记录应该是工具，不是负担。\n"
            "随时回来继续记录，不需要赶上之前的。"
        ),
        False,
    ),
    # —— anxiety / stress ——
    (
        ["焦虑", "压力大", "压力很大", "烦躁", "情绪化进食", "情绪化", "不开心"],
        "anxious",
        (
            "注意到了情绪的波动，这很重要。压力和饮食确实紧密相关。\n"
            "试试深呼吸几次，或出去走几分钟——不是为了消耗热量，只是换个环境。\n"
            "想聊聊也可以，我会在这儿。"
        ),
        False,
    ),
    # —— positive reinforcement ——
    (
        ["今天很健康", "特别健康", "挺健康", "很健康", "坚持住了", "坚持了", "做到了",
         "控制住了", "没吃零食", "健康的一餐", "自律", "健康饮食"],
        "positive",
        (
            "做得好！每一餐的健康选择都在积累。\n"
            "这种正向循环比任何短期数字都重要。"
        ),
        False,
    ),
    (
        ["达成目标", "达标", "刚好", "完美"],
        "positive",
        (
            "很棒！今天的记录看起来很均衡。\n"
            "记住这种状态——它是可持续的生活方式，不是短期的'坚持'。"
        ),
        False,
    ),
    # —— illness ——
    (
        ["感冒", "发烧", "生病", "不舒服", "拉肚子", "头疼", "头痛", "肚子疼"],
        "illness",
        (
            "生病期间优先恢复，暂停严格的热量追踪。多休息，多喝水。\n"
            "身体需要能量来康复——现在不是限制饮食的时候。\n"
            "等好了再继续记录也不迟。"
        ),
        True,
    ),
    (
        ["没胃口", "吃不下", "不想吃", "恶心", "想吐"],
        "illness",
        (
            "没胃口的时候就先不勉强。少量多餐，选容易消化的食物。\n"
            "记录低摄入日没问题——身体今天有更重要的事要做。"
        ),
        False,
    ),
    # —— sleep / fatigue ——
    (
        ["失眠", "熬夜", "睡不好", "一夜没睡", "睡眠不足"],
        "negative",
        (
            "睡眠不足确实会打乱饮食节奏。研究显示缺觉会让人更想吃高热量食物。\n"
            "今天可以适度放宽碳水摄入，帮助身体应对疲劳。\n"
            "今晚优先早点休息。"
        ),
        False,
    ),
    # —— eating disorder red flags ——
    (
        ["催吐", "泻药", "绝食", "不吃了", "一天不吃", "断食好几天"],
        "anxious",
        (
            "我注意到一些让我担心的信号。极端限制可能会带来健康风险。\n"
            "如果需要专业支持，可以联系注册营养师或心理咨询师。\n"
            "我的角色是记录饮食，不能替代专业帮助——但我关心你的健康。"
        ),
        True,
    ),
    # —— all-or-nothing thinking ——
    (
        ["反正已经吃了", "不管了", "算了", "明天再开始", "下周再开始"],
        "guilty",
        (
            "不需要等'明天重新开始'。下一餐就可以回到计划。\n"
            "不是'完美的一天'就是'毁掉的一天'——这是全有全无思维。\n"
            "没有完美的饮食，只有持续的大方向。"
        ),
        False,
    ),
]


def detect_emotion(text: str) -> EmotionResult | None:
    """Scan user text for emotional/psychological signals.  Returns None if neutral.

    This is a rule-based detector — fast, deterministic, no LLM cost.
    More nuanced detection can use DeepSeek.classify_intent() as a supplement.
    """
    if not text or not text.strip():
        return None

    best_match: tuple[int, EmotionResult] | None = None

    for keywords, tone, response, block in EMOTION_PATTERNS:
        matched = [kw for kw in keywords if kw in text]
        if matched:
            # Longer keyword = stronger signal; blocking patterns get bonus priority
            score = sum(len(kw) for kw in matched)
            if block:
                score += 10  # blocking patterns win ties against non-blocking
            result = EmotionResult(
                tone=tone,
                keywords=matched,
                response=response,
                should_block_meal_parsing=block,
            )
            if best_match is None or score > best_match[0]:
                best_match = (score, result)

    return best_match[1] if best_match else None
