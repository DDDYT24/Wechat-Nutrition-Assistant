---
name: track-healthy-diet
description: Record and review an adult user's meals with consented profile onboarding, controlled food or package-label data, deterministic calorie and macronutrient calculations, meal-period and daily balances, explicit uncertainty, weight trends, nutrient-gap summaries, and weekly reviews. Use for food logging, calorie or macro calculation, healthy-diet monitoring, meal feedback, nutrition target tracking, or when operating the WeChat Nutrition Tools MCP. Do not use as a substitute for diagnosis, medical nutrition therapy, medication changes, or emergency care.
---

# Track Healthy Diet

Use the model for language understanding and explanation. Use controlled tools for every nutrition number.

## Core workflow

1. Call `get_onboarding_status` before personalized targets or the first saved meal in the WeChat workflow.
2. If consent is missing, explain the data purpose and deletion option. Call `begin_onboarding` only after explicit consent.
3. Merge only explicitly provided fields with `record_profile_input`. Present every captured value and call `confirm_profile` only after the user explicitly confirms it.
4. Determine whether the user wants to estimate, calculate, save, or review a meal.
5. Call `parse_meal` to extract foods, explicit weights, brands, and cooking methods. Pass `user_id` when personal package-label foods may apply.
6. Ask one concise clarification when grams, edible portion, oil, sauce, raw/cooked state, or a broad category such as “巧克力” materially affects the result.
7. Call `lookup_food` for uncertain public-catalog matches. Never substitute a model-generated nutrient value for an unresolved food.
8. If a packaged food is missing, use `register_custom_food` only from explicit per-100g label values. Never infer an absent calorie or macro value.
9. Call `calculate_meal` only after food identity and grams are explicit.
10. Call `save_meal` only when the user asked to record the meal or the active product workflow clearly records submitted meals.
11. Immediately show the saved meal period, meal totals, daily calories, protein, fat and carbohydrate, plus remaining targets when available.
12. Use `get_daily_balance`, `get_nutrient_gap`, `generate_weekly_review`, and weight-trend tools only from saved records.

Read [references/tool-contracts.md](references/tool-contracts.md) before the first nutrition MCP call in a task. Read [references/safety.md](references/safety.md) before personalized recommendations or whenever the user mentions age, pregnancy, disease, medication, allergy, disordered eating, or severe symptoms.

## Accuracy rules

- Treat packaged-label data plus consumed grams as the strongest V1.1 input.
- Treat weighed ingredients and explicit cooking oil as calculable inputs.
- Treat bowls, portions, restaurant dishes, and photos without scale references as estimates requiring clarification or a range.
- Never report false precision. Round meal energy to whole kcal and macros to one decimal place for display.
- Keep raw and cooked weights distinct.
- Do not silently add oil, sauces, sugar, discarded bones, or inedible portions.
- Refuse to save calculated totals when any item remains unresolved.

## Response pattern

Keep routine replies compact:

1. State what was recognized.
2. State the calculated totals.
3. State the largest uncertainty or data limitation.
4. Give at most two practical general-health suggestions.

When grams are missing, ask for them instead of calculating. Example: “这份米饭和鸡胸肉分别大约多少克？没有重量时我不会输出伪精确热量。”

## Profile and privacy

- Require explicit consent before collecting health-profile fields.
- Accept profile details in any order and across multiple turns, but always show a full confirmation summary before deriving targets.
- Use `calculate_energy_targets` only as a preview. Use `confirm_profile` for the saved Mifflin–St Jeor + PAL result.
- Describe Mifflin–St Jeor and PAL as an initial estimate, not a measured metabolism or guaranteed outcome.
- Describe V1.1 goal adjustments (-15% for fat loss, +8% for muscle gain) as product defaults, not medical formulas.
- Do not derive a treatment target from a diagnosis.
- Use `record_weight` and `get_weight_trend` for trends. Do not recalibrate from fewer than 14 observations or incomplete food logs.
- Use `delete_user_data` only after explicit confirmation because it is irreversible.

## Boundaries

Limit automated V1.1 targets to general healthy adults. For excluded or high-risk situations, follow [references/safety.md](references/safety.md), keep recording separate from advice, and recommend an appropriate qualified professional when necessary.
