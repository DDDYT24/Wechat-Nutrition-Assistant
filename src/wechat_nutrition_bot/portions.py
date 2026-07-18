"""Portion and unit conversion engine for V1.2.

Resolves natural-language units (个/碗/杯/片/颗/勺/块/根/包/瓶/份),
vague quantifiers (几口/一半/大半), and composite foods (麻辣烫/火锅/烧烤)
into estimated gram weights — always with an explicit confidence level.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PortionEstimate:
    grams: float
    confidence: float  # 0.0–1.0
    unit_used: str
    note: str = ""


# ── Layer 1: natural unit → per-food default grams ──────────────────────────
# Keys are unit names; values are {food_keyword: default_grams}.
# "food_keyword" is matched case-insensitively against the food name/alias.

NATURAL_UNITS: dict[str, dict[str, float]] = {
    "个": {
        "鸡蛋": 50, "鸭蛋": 65, "鹌鹑蛋": 10, "鹅蛋": 120,
        "苹果": 200, "梨": 200, "橘子": 150, "橙": 200, "桃子": 180,
        "猕猴桃": 80, "芒果": 250, "柠檬": 80, "柿子": 150,
        "馒头": 100, "包子": 80, "饺子": 25, "汤圆": 20, "烧麦": 40,
        "虾饺": 25, "小笼包": 35, "粽子": 120, "月饼": 80, "春卷": 50,
        "土豆": 150, "番茄": 150, "洋葱": 200, "红薯": 200,
        "面包": 60, "蛋挞": 70, "麻团": 45, "肉丸": 20,
    },
    "片": {
        "吐司": 30, "面包": 30, "三文鱼": 15, "刺身": 15,
        "火腿": 20, "芝士": 20, "奶酪": 20, "培根": 15,
        "饼干": 10, "薯片": 2, "牛肉": 15, "猪肉": 15,
        "午餐肉": 20, "腊肉": 15, "血豆腐": 20,
    },
    "碗": {
        "米饭": 150, "粥": 300, "稀饭": 300, "面条": 250,
        "汤": 250, "麦片": 40, "馄饨": 250, "豆花": 280,
        "面": 250, "粉": 250, "米线": 250, "酸辣粉": 300,
    },
    "杯": {
        "牛奶": 250, "豆浆": 300, "咖啡": 350, "酸奶": 200,
        "果汁": 300, "奶茶": 500, "水": 300, "茶": 300,
        "奶昔": 350, "可可": 250, "豆奶": 250,
    },
    "勺": {
        "烹调油": 8, "食用油": 8, "油": 8, "白糖": 10,
        "花生酱": 15, "蛋白粉": 30, "蜂蜜": 15, "果酱": 15,
        "沙拉酱": 15, "芝麻酱": 15, "盐": 5, "酱油": 10,
        "醋": 10, "料酒": 10,
    },
    "块": {
        "红烧肉": 25, "豆腐": 100, "牛排": 200, "鸡胸肉": 150,
        "巧克力": 10, "黄油": 15, "奶酪": 25, "蛋糕": 80,
        "西瓜": 300, "南瓜": 150, "红薯": 100,
    },
    "根": {
        "香蕉": 120, "黄瓜": 200, "玉米": 200, "胡萝卜": 100,
        "香肠": 50, "火腿肠": 50, "油条": 70, "年糕": 100,
        "芹菜": 80, "山药": 150,
    },
    "颗": {
        "杏仁": 1.2, "花生": 1.0, "葡萄": 5, "草莓": 20,
        "蓝莓": 2, "红枣": 10, "腰果": 1.5, "核桃": 15,
        "开心果": 1.2, "夏威夷果": 4, "桂圆": 8, "荔枝": 25,
        "樱桃": 5, "车厘子": 10, "圣女果": 15, "枸杞": 0.5,
        "话梅": 5, "糖": 4,
    },
    "包": {
        "方便面": 100, "薯片": 75, "饼干": 100, "辣条": 50,
        "坚果": 25, "瓜子": 30, "糖果": 50, "巧克力": 50,
        "海苔": 5, "牛肉干": 50, "豆干": 80,
    },
    "瓶": {
        "啤酒": 500, "可乐": 500, "雪碧": 500, "矿泉水": 550,
        "纯净水": 550, "饮料": 500, "功能饮料": 500, "茶饮料": 500,
        "果汁": 450, "豆奶": 300, "酸奶": 250,
    },
    "盒": {
        "酸奶": 150, "牛奶": 250, "便当": 400, "豆腐": 400,
        "寿司": 200, "沙拉": 250, "水果": 200, "冰淇淋": 200,
    },
    "份": {
        "食堂菜": 150, "外卖菜": 200, "凉菜": 120, "热菜": 180,
        "盖浇饭": 500, "炒饭": 450, "炒面": 400, "盒饭": 500,
        "套餐": 550, "火锅": 800, "冒菜": 500,
    },
    "把": {
        "花生": 30, "瓜子": 25, "坚果": 30, "葡萄干": 30,
        "枸杞": 15, "红枣": 40, "杏仁": 25,
    },
    "罐": {
        "可乐": 330, "雪碧": 330, "啤酒": 330, "八宝粥": 360,
        "午餐肉": 200, "豆豉鲮鱼": 180,
    },
}


# ── Layer 2: vague quantifiers → fraction of default portion ─────────────────
VAGUE_QUANTIFIERS: dict[str, float] = {
    "一口": 0.05, "几口": 0.10, "尝了一点": 0.08,
    "一点": 0.15, "一点点": 0.10, "一些": 0.20, "少许": 0.15,
    "小半": 0.30, "小半碗": 0.30, "小半份": 0.30,
    "半": 0.50, "一半": 0.50, "半碗": 0.50, "半份": 0.50,
    "大半": 0.70, "大半碗": 0.70, "大半份": 0.70,
    "大部分": 0.80, "差不多": 0.75, "大概": 0.70,
    "几乎全部": 0.90, "基本上": 0.85, "剩了一点": 0.85,
    "快吃完了": 0.88, "吃了不少": 0.75,
    "一些些": 0.20, "不多": 0.25, "挺多": 0.75,
}


# ── Layer 3: composite / restaurant foods ────────────────────────────────────
@dataclass
class CompositeFood:
    name: str
    default_grams: float = 0
    default_kcal: float = 0
    uncertainty: str = "medium"  # low / medium / high
    prompt: str = ""
    aliases: list[str] = field(default_factory=list)


COMPOSITE_FOODS: dict[str, CompositeFood] = {}
for _cf in [
    CompositeFood("麻辣烫", 500, 0, "high", "大概放了哪些食材？荤多还是素多？",
                   ["麻辣燙"]),
    CompositeFood("火锅", 800, 0, "high", "主要吃了什么肉类和蔬菜？锅底是什么？"),
    CompositeFood("烧烤", 400, 0, "high", "吃了哪些种类？肉串多还是蔬菜多？",
                   ["烤肉", "BBQ"]),
    CompositeFood("麻辣香锅", 500, 0, "high", "选了哪些食材？"),
    CompositeFood("冒菜", 500, 0, "high", "放了哪些菜？"),
    CompositeFood("食堂套餐", 600, 0, "medium", "大概有哪些菜？"),
    CompositeFood("外卖便当", 500, 0, "medium", "",
                   ["外卖", "便当", "盒饭"]),
    CompositeFood("便利店饭团", 110, 0, "low", "是什么口味的？",
                   ["饭团", "三角饭团"]),
    CompositeFood("三明治", 200, 0, "medium", "",
                   ["三文治"]),
    CompositeFood("沙拉", 350, 0, "medium", "加了什么酱料？"),
    CompositeFood("汉堡套餐", 0, 750, "medium", "是哪个品牌的？含薯条和可乐吗？",
                   ["汉堡", "汉堡包"]),
    CompositeFood("披萨", 200, 0, "medium", "大概吃了几片？什么口味？",
                   ["比萨", "pizza"]),
    CompositeFood("寿司", 200, 0, "medium", "大概吃了几个？什么种类？",
                   ["日本寿司", "握寿司"]),
    CompositeFood("日料定食", 500, 0, "medium", "",
                   ["日式定食", "日本料理"]),
    CompositeFood("盖浇饭", 500, 0, "medium", "是什么浇头？",
                   ["盖饭", "盖码饭"]),
    CompositeFood("炒饭", 450, 0, "medium", "是什么炒饭？"),
    CompositeFood("炒面", 400, 0, "medium", ""),
    CompositeFood("炒粉", 400, 0, "medium", ""),
    CompositeFood("馄饨", 250, 0, "low", "大概多少个？什么馅？",
                   ["云吞", "抄手"]),
    CompositeFood("水饺", 250, 0, "low", "大概多少个？什么馅？",
                   ["饺子"]),
    CompositeFood("包子", 100, 0, "low", "什么馅？",
                   ["肉包", "菜包", "小笼包"]),
    CompositeFood("煎饼果子", 250, 0, "medium", "",
                   ["煎饼"]),
    CompositeFood("肉夹馍", 180, 0, "medium", ""),
    CompositeFood("凉皮", 350, 0, "medium", "加了什么调料？"),
    CompositeFood("酸辣粉", 400, 0, "medium", ""),
    CompositeFood("螺蛳粉", 400, 0, "medium", ""),
    CompositeFood("米线", 400, 0, "medium", "",
                   ["过桥米线"]),
    CompositeFood("肠粉", 300, 0, "medium", "是什么馅的？"),
    CompositeFood("粽子", 150, 0, "low", "甜的还是咸的？"),
    CompositeFood("汤圆", 200, 0, "low", "什么馅的？",
                   ["元宵"]),
]:
    for _name in {_cf.name, *_cf.aliases}:
        COMPOSITE_FOODS[_name] = _cf


# ── Resolver ─────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return "".join(text.lower().strip().split())


class PortionResolver:
    """Stateless resolver: food name + amount + unit → estimated grams."""

    @staticmethod
    def resolve(
        food_name: str,
        amount: float | None = None,
        unit: str | None = None,
    ) -> PortionEstimate | None:
        """Return a gram estimate when the unit is a natural-language measure.

        Args:
            food_name: canonical or alias name of the food
            amount: numeric quantity (e.g. 2 for "2个")
            unit: natural unit string (个/碗/杯/…)  —  None means 'check for vague quantifiers'

        Returns:
            PortionEstimate or None when this unit is not recognized.
        """
        if not food_name or not amount or amount <= 0:
            return None

        # ── exact gram units (passthrough) ──
        if unit and unit.lower() in {"g", "克", "gram", "grams"}:
            return PortionEstimate(grams=amount, confidence=1.0, unit_used="g")

        if unit and unit.lower() in {"kg", "公斤", "千克"}:
            return PortionEstimate(grams=amount * 1000, confidence=1.0, unit_used="kg")

        if unit and unit.lower() in {"ml", "毫升"}:
            # rough: most beverages are ~1 g/ml
            return PortionEstimate(grams=amount, confidence=0.85, unit_used="ml",
                                   note="ml→g 按密度 1.0 估算，高脂/高糖液体可能偏轻")

        # ── natural units ──
        if unit and unit in NATURAL_UNITS:
            unit_map = NATURAL_UNITS[unit]
            norm_food = _normalize(food_name)
            # exact match first
            for key, grams in unit_map.items():
                nk = _normalize(key)
                if nk == norm_food or nk in norm_food or norm_food in nk:
                    return PortionEstimate(
                        grams=round(grams * amount, 1),
                        confidence=0.85,
                        unit_used=unit,
                        note=f"默认 1{unit}={grams}g",
                    )
            # no food match → generic default for this unit
            generic_defaults = {
                "个": 100, "片": 25, "碗": 250, "杯": 250,
                "勺": 10, "块": 80, "根": 100, "颗": 5,
                "包": 80, "瓶": 500, "盒": 200, "份": 250,
                "把": 30, "罐": 350,
            }
            if unit in generic_defaults:
                return PortionEstimate(
                    grams=round(generic_defaults[unit] * amount, 1),
                    confidence=0.5,
                    unit_used=unit,
                    note=f"使用通用 1{unit}={generic_defaults[unit]}g（非特定食物默认值）",
                )

        # ── vague quantifier in text (unit IS the quantifier) ──
        # This handles cases like "吃了几口米饭" where "几口" = 0.10 of a standard portion
        if unit and unit in VAGUE_QUANTIFIERS:
            fraction = VAGUE_QUANTIFIERS[unit]
            # try to find the food's standard portion
            default_grams = _default_portion_for(food_name)
            if default_grams:
                return PortionEstimate(
                    grams=round(default_grams * fraction * amount, 1),
                    confidence=0.35,
                    unit_used=unit,
                    note=f"模糊量化'{unit}'={int(fraction*100)}%×标准份量{default_grams}g",
                )

        return None

    @staticmethod
    def get_composite(food_name: str) -> CompositeFood | None:
        """Return composite-food metadata when the name matches."""
        norm = _normalize(food_name)
        for key, cf in COMPOSITE_FOODS.items():
            if _normalize(key) == norm or _normalize(key) in norm or norm in _normalize(key):
                return cf
        return None

    @staticmethod
    def estimate_range(grams: float, confidence: float) -> tuple[float, float]:
        """Convert a point estimate + confidence into a display range.

        Low confidence → wider range.
        """
        if confidence >= 0.9:
            return (grams * 0.95, grams * 1.05)
        if confidence >= 0.7:
            return (grams * 0.85, grams * 1.15)
        if confidence >= 0.5:
            return (grams * 0.75, grams * 1.25)
        return (grams * 0.6, grams * 1.4)


def _default_portion_for(food_name: str) -> float | None:
    """Heuristic: guess a standard single-serving gram weight for any food."""
    norm = _normalize(food_name)
    # check all unit maps for this food
    for unit_map in NATURAL_UNITS.values():
        for key, grams in unit_map.items():
            if _normalize(key) in norm or norm in _normalize(key):
                return grams
    # broad category heuristics
    if any(t in norm for t in ("肉", "鸡", "鸭", "鱼", "虾", "蟹", "贝", "牛", "羊", "猪")):
        return 150  # typical cooked meat serving
    if any(t in norm for t in ("菜", "蔬菜", "叶", "瓜", "花", "豆角", "椒")):
        return 200
    if any(t in norm for t in ("饭", "面", "粉", "米", "饼", "包", "馒头")):
        return 200
    if any(t in norm for t in ("奶", "浆", "汁", "茶", "咖", "饮")):
        return 250
    return None
