"""V1.2 Exercise & activity tracking module.

Handles training sessions, daily steps, and exercise-related energy adjustments.
Training expenditure is recorded but NOT automatically added to food budgets
(users must opt in) — to avoid the "I trained so I can eat more" trap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .models import IntentExercise

# ── constants ────────────────────────────────────────────────────────────────

# MET-based estimates for common activities (kcal/kg/hour)
ACTIVITY_MET: dict[str, float] = {
    "力量训练": 5.0,
    "有氧": 7.0,
    "HIIT": 10.0,
    "跑步": 8.0,
    "游泳": 7.0,
    "骑行": 6.0,
    "瑜伽": 3.0,
    "柔韧": 3.0,
    "散步": 3.5,
    "普拉提": 3.5,
    "其他": 4.0,
}

# Per-step kcal estimate (avg 0.04 kcal/step for a 70kg adult)
KCAL_PER_STEP = 0.04

# Protein multiplier for training days (g protein per kg body weight)
PROTEIN_TRAINING_FACTOR = 2.0   # up from 1.6 default
PROTEIN_REST_FACTOR = 1.2


@dataclass
class ExerciseSession:
    """A single training or activity session."""
    date: date
    type: str                    # "力量训练" | "有氧" | "HIIT" | "柔韧" | "其他"
    duration_minutes: int = 0
    intensity: str = "中"        # "低" | "中" | "高"
    body_part: str | None = None  # "胸三头" | "背二头" | "腿" | "肩" | "全身" | ...
    exercises: list[str] = field(default_factory=list)
    steps: int | None = None
    notes: str = ""


class ExerciseService:
    """Training & activity service — stateless, all persistence via repository."""

    @staticmethod
    def estimate_training_kcal(
        session_type: str, duration_minutes: int, weight_kg: float, intensity: str = "中"
    ) -> float:
        """Estimate kcal burned during a training session using MET values.

        kcal = MET × weight_kg × (duration_hours)
        Intensity modifiers: 低=0.8, 中=1.0, 高=1.2
        """
        met = ACTIVITY_MET.get(session_type, 4.0)
        intensity_mod = {"低": 0.8, "中": 1.0, "高": 1.2}.get(intensity, 1.0)
        hours = duration_minutes / 60
        return round(met * weight_kg * hours * intensity_mod)

    @staticmethod
    def estimate_steps_kcal(steps: int, weight_kg: float | None = None) -> float:
        """Estimate kcal from step count.  Weight-adjusted when available."""
        factor = KCAL_PER_STEP * (weight_kg / 70) if weight_kg else KCAL_PER_STEP
        return round(steps * factor)

    @staticmethod
    def suggested_protein(
        weight_kg: float,
        training_today: bool = False,
        goal: str = "maintain",
    ) -> float:
        """Daily protein recommendation in grams.

        Training day: 2.0 g/kg (cutting) or 1.8 g/kg (maintenance/bulk)
        Rest day: 1.6 g/kg (cutting) or 1.2 g/kg (maintenance/bulk)
        """
        if training_today:
            factor = PROTEIN_TRAINING_FACTOR if goal == "lose" else 1.8
        else:
            factor = 1.6 if goal == "lose" else PROTEIN_REST_FACTOR
        return round(weight_kg * factor, 1)

    @staticmethod
    def parse_training_text(text: str) -> ExerciseSession | None:
        """Rule-based training-text extraction.  Fallback when DeepSeek unavailable.

        Recognizes patterns like:
        - "练胸和三头，90分钟，中高强度"
        - "今日步数 12000"
        - "跑步30分钟"
        """
        import re

        steps_match = re.search(r"(?:今日)?步数\s*[:：]?\s*(\d+)", text)
        steps = int(steps_match.group(1)) if steps_match else None

        # Detect training type
        training_type = "其他"
        detected_parts: list[str] = []
        chest_arm = ("练胸", "卧推", "飞鸟", "俯卧撑", "推举", "三头", "二头", "手臂")
        if any(t in text for t in chest_arm):
            training_type = "力量训练"
            detected_parts.extend(["胸", "三头"] if "三头" in text else ["胸"])
        if any(t in text for t in ("练腿", "深蹲", "硬拉", "腿举", "箭步")):
            training_type = "力量训练"
            detected_parts.append("腿")
        if any(t in text for t in ("练背", "引体", "划船", "下拉")):
            training_type = "力量训练"
            detected_parts.append("背")
        if any(t in text for t in ("跑步", "快走", "慢跑")):
            training_type = "有氧" if training_type == "其他" else training_type
        if any(t in text for t in ("hiit", "HIIT", "间歇", "高强度间歇")):
            training_type = "HIIT"
        if any(t in text for t in ("瑜伽", "拉伸")):
            training_type = "柔韧"
        if any(t in text for t in ("游泳",)):
            training_type = "有氧"

        duration = None
        dur_match = re.search(r"(\d+)\s*(?:分钟|min)", text)
        if dur_match:
            duration = int(dur_match.group(1))

        intensity = "中"
        if any(t in text for t in ("高强度", "很累", "力竭", "全力")):
            intensity = "高"
        elif any(t in text for t in ("低强度", "轻松", "恢复")):
            intensity = "低"

        # Only create a session if there's actual training content or steps
        if duration or steps or training_type != "其他" or detected_parts:
            return ExerciseSession(
                date=date.today(),
                type=training_type,
                duration_minutes=duration or 0,
                intensity=intensity,
                body_part="+".join(detected_parts) if detected_parts else None,
                steps=steps,
                notes=text[:200],
            )
        return None

    @staticmethod
    def from_structured(data: IntentExercise, source_text: str) -> ExerciseSession:
        """Convert validated language fields to a session without accepting energy numbers."""
        return ExerciseSession(
            date=date.today(),
            type=data.type,
            duration_minutes=data.duration_minutes or 0,
            intensity=data.intensity,
            body_part="+".join(data.body_parts) if data.body_parts else None,
            exercises=data.exercises,
            steps=data.steps,
            notes=source_text[:200],
        )

    @staticmethod
    def format_session_reply(session: ExerciseSession, weight_kg: float | None = None) -> str:
        """Generate a human-friendly reply for a recorded training session."""
        lines = ["训练已记录"]
        parts: list[str] = []
        if session.body_part:
            parts.append(session.body_part)
        if session.type:
            parts.append(session.type)
        if session.duration_minutes:
            parts.append(f"{session.duration_minutes}分钟")
        if session.intensity:
            parts.append(f"{session.intensity}强度")
        lines.append("  " + " · ".join(parts))

        if weight_kg and session.duration_minutes:
            kcal = ExerciseService.estimate_training_kcal(
                session.type, session.duration_minutes, weight_kg, session.intensity
            )
            lines.append(
                f"  估算训练消耗约 {kcal} kcal（仅供参考，不作为热量补偿依据）"
            )

        if session.steps:
            steps_kcal = ExerciseService.estimate_steps_kcal(session.steps, weight_kg)
            lines.append(f"  今日步数 {session.steps} · 估算消耗约 {steps_kcal} kcal")

        if weight_kg:
            has_training = session.duration_minutes > 0
            protein = ExerciseService.suggested_protein(weight_kg, has_training)
            lines.append(f"  今日蛋白质建议：{protein}g{'（训练日加成）' if has_training else ''}")

        return "\n".join(lines)
