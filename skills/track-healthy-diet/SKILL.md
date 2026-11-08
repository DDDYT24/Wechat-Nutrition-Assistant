---
name: track-healthy-diet
description: Record and review an adult user's meals and exercise through the WeChat Nutrition Assistant V1.2. Use for mixed meal-and-training messages, unknown-food estimation, calorie or macro calculation, remaining-calorie questions, next-meal suggestions, daily balances, nutrition targets, weight trends, or weekly reviews. Prefer catalog and package-label data, allow clearly labeled model estimates for unresolved foods, and use saved records for daily totals. Do not use for diagnosis, medical nutrition therapy, medication changes, or emergency care.
---

# Track Healthy Diet

Use the model to understand simultaneous intents, estimate unresolved foods, and answer meal-planning questions. Prefer controlled catalog or package-label values. Use saved database records for daily totals and deterministic MET rules for exercise expenditure.

Read [references/tool-contracts.md](references/tool-contracts.md) before the first MCP call. Read [references/safety.md](references/safety.md) before personalized recommendations or whenever age, pregnancy, disease, medication, allergy, disordered eating, or severe symptoms appear.

## Process every intent

1. Extract all intents before acting. Do not stop after finding training when the same message also contains food.
2. Keep each meal phrase and exercise phrase tied to its exact source span.
3. Process every recognized intent independently, then combine the confirmed results into one reply.
4. Reuse one stable `source_message_id` for every write caused by the same incoming message so delivery retries remain idempotent.

## Resolve and record meals

1. Call `get_onboarding_status` before personalized targets or the first saved meal. Collect and confirm profile data only after explicit consent.
2. Call `parse_meal` for the exact meal span. Treat one source mention as at most one food item.
3. Prefer the longest non-overlapping catalog match. Never match a shorter alias inside a longer recognized food, such as `鸡` inside `鸡蛋`.
4. Map a generic name to a controlled `代表值` when available. Otherwise call the configured model for a common-portion and nutrition estimate.
5. Label model-derived foods as estimates and retain their assumptions and confidence. Prefer an explicit package label whenever the user provides one.
6. Estimate missing common portions when reasonable; ask only when the request cannot be interpreted or the estimate fails validation.
7. Call `calculate_meal` only for fully resolved catalog identifiers and grams. Call `save_meal` only when recording is requested by the active workflow.

## Resolve and record exercise

1. Extract only type, duration, intensity, body parts, exercise names, steps, and time.
2. Call `record_exercise`; never send calories or another expenditure estimate as input.
3. Use `get_daily_exercise` for reviews. Keep exercise expenditure separate from food intake and never add it automatically to the eating budget.

## Numeric sources

- Prefer catalog and package-label nutrition values over model estimates.
- Allow the model to estimate grams and per-100g nutrition only for unresolved foods. Validate bounds and mark persisted results as `estimated`.
- Never let the model generate exercise expenditure; use the exercise service.
- Use `get_daily_balance`, `get_nutrient_gap`, `generate_weekly_review`, `get_daily_exercise`, and weight tools only from saved database records.
- Answer remaining-calorie and next-meal questions with the model using saved intake, targets, allergies, preferences, and goals as context.
- Round only for display: energy to whole kcal and macros to one decimal place.

## Reply compactly

State what was recorded, distinguish catalog values from model estimates, name the largest assumption, and give at most two practical suggestions.

## Privacy and safety

Use a stable pseudonymous `user_id`, not a name, phone number, medical-record number, or raw contact identifier. Require explicit confirmation before `delete_user_data`. Treat Mifflin–St Jeor plus PAL as an initial estimate and product defaults as non-medical guidance.
