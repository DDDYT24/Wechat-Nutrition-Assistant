"""V1.2 Supplement catalog.

Common fitness & health supplements with default per-serving nutrition data.
Users can override with actual package labels via the custom-food registration flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Supplement:
    name: str
    aliases: list[str] = field(default_factory=list)
    default_unit: str = "勺"         # natural unit for this supplement
    grams_per_unit: float = 30       # default grams per unit
    kcal_per_unit: float = 0         # kcal per default serving
    protein_g_per_unit: float = 0
    fat_g_per_unit: float = 0
    carb_g_per_unit: float = 0
    category: str = "补充剂"
    notes: str = ""


# ── catalog ──────────────────────────────────────────────────────────────────
# Values are typical / conservative estimates.  Users should register their
# specific product for accurate numbers.

SUPPLEMENTS: dict[str, Supplement] = {}

_raw_supplements = [
    Supplement("蛋白粉", ["乳清蛋白", "蛋白质粉", "蛋白粉"], "勺", 30, 120, 24, 1.5, 3,
               notes="以常见乳清蛋白为准；植物蛋白数值不同"),
    Supplement("增肌粉", ["增重粉", "mass gainer", "增肌粉"], "勺", 100, 380, 20, 4, 60,
               notes="碳水比例高，用于增肌期热量盈余"),
    Supplement("酪蛋白", ["casein", "缓释蛋白"], "勺", 30, 110, 24, 1, 2,
               notes="消化慢，适合睡前使用"),
    Supplement("肌酸", ["creatine", "一水肌酸"], "勺", 5, 0, 0, 0, 0,
               notes="不影响热量计算；建议每日5g"),
    Supplement("BCAA", ["支链氨基酸", "bcaa"], "勺", 5, 20, 5, 0, 0,
               notes="实际热量来自蛋白质（每克4kcal已计入）"),
    Supplement("EAA", ["必需氨基酸", "eaa"], "勺", 10, 40, 10, 0, 0),
    Supplement("preworkout", ["氮泵", "pre", "预训练", "pre-workout"], "勺", 10, 5, 0, 0, 1,
               notes="含咖啡因；个体反应差异大"),
    Supplement("谷氨酰胺", ["glutamine", "谷氨"], "勺", 5, 20, 5, 0, 0),
    Supplement("ZMA", ["锌镁片", "锌镁", "zma"], "粒", 1, 0, 0, 0, 0,
               notes="睡前补充剂，不影响热量"),
    Supplement("鱼油", ["fish oil", "omega3", "欧米伽3"], "粒", 1, 10, 0, 1, 0,
               notes="每粒约1g；品牌差异大"),
    Supplement("维生素D", ["vd", "维生素d", "维D"], "粒", 1, 0, 0, 0, 0),
    Supplement("复合维生素", ["multivitamin", "多维", "综合维生素"], "粒", 1, 0, 0, 0, 0),
    Supplement("褪黑素", ["melatonin", "睡眠片"], "粒", 1, 0, 0, 0, 0,
               notes="不影响热量；短期使用建议"),
    Supplement("左旋肉碱", ["l-carnitine", "肉碱"], "粒", 1, 0, 0, 0, 0,
               notes="效果因人而异"),
    Supplement("CLA", ["共轭亚油酸", "cla"], "粒", 1, 10, 0, 1, 0),
    Supplement("氮泵", [], "勺", 10, 5, 0, 0, 1,
               notes="同 preworkout；含咖啡因"),
]

# Build lookup dict keyed by normalized name + aliases
for _sup in _raw_supplements:
    for _name in {_sup.name, *_sup.aliases}:
        SUPPLEMENTS[_name.lower().strip()] = _sup


def lookup_supplement(name: str) -> Supplement | None:
    """Find a supplement by name or alias.  Case-insensitive."""
    return SUPPLEMENTS.get(name.lower().strip())


def resolve_supplement_grams(name: str, amount: float, unit: str) -> tuple[float, float, str] | None:
    """Convert supplement amount+unit to estimated grams and kcal.

    Returns (grams, kcal, note) or None if not found.
    """
    sup = lookup_supplement(name)
    if not sup:
        return None
    if unit in {"勺", "scoop", "匙"}:
        grams = amount * sup.grams_per_unit
        kcal = amount * sup.kcal_per_unit
    elif unit in {"粒", "颗", "片", "capsule", "tablet"}:
        grams = amount * sup.grams_per_unit
        kcal = amount * sup.kcal_per_unit
    elif unit in {"g", "克"}:
        # Direct grams — scale per-unit values
        grams = amount
        ratio = amount / sup.grams_per_unit if sup.grams_per_unit else 1
        kcal = ratio * sup.kcal_per_unit
    else:
        # Unknown unit, try default
        grams = amount * sup.grams_per_unit
        kcal = amount * sup.kcal_per_unit
    return (round(grams, 1), round(kcal), sup.notes)
