# Nutrition MCP tool contracts

## General contract

- Pass a stable pseudonymous `user_id`; do not pass names, phone numbers, medical record numbers, or raw contact details.
- Treat every tool result as the nutrition source of truth.
- Do not overwrite tool numbers with model estimates.
- Surface `unresolved`, `warnings`, `data_status`, and `notes` to the user when material.

## Tools

### `lookup_food(query, limit=5)`

Search before calculating when a food name is ambiguous. Prefer exact matches. Check raw/cooked state and notes.

### `get_onboarding_status(user_id)` / `begin_onboarding(user_id)`

Check status first. `begin_onboarding` records consent, so call it only after the user explicitly agrees to the stated data use.

### `record_profile_input(user_id, updates)` / `confirm_profile(user_id)`

Merge only explicit values. Values remain a draft until the user reviews the complete summary and explicitly confirms. `confirm_profile` derives and saves initial targets deterministically.

### `calculate_energy_targets(profile)`

Preview only. Requires a complete adult profile and returns formula version, REE, PAL, maintenance estimate, product goal adjustment, macros, assumptions, and warnings.

### `parse_meal(text, user_id?)`

Extract only explicitly stated information. A `grams: null` result requires clarification. Parsing does not calculate nutrition.

### `calculate_meal(items, user_id?)`

Each item requires `food_id` or controlled `name`, plus positive `grams`. Use this for preview without persistence. Do not describe `partial` as a complete meal total.

### `save_meal(user_id, items, eaten_at?, note?, source_message_id?)`

Save only resolved items. Reuse `source_message_id` for idempotency when a channel retries delivery. The response includes `meal_period`, classified in Asia/Shanghai.

### `get_daily_balance(user_id, day?)`

Interpret `remaining` only when complete confirmed targets exist. Missing targets are not zero targets. `by_meal_period` contains breakfast, lunch, afternoon, and evening totals.

### `get_nutrient_gap(user_id, start_date, end_date)`

Check `days_with_records`. Missing days can make averages look artificially low.

### `generate_weekly_review(user_id, week_start?)`

Summarize recorded behavior, not unobserved intake. Do not diagnose deficiency from food logs alone.

### `upsert_profile(user_id, profile)`

Compatibility tool only. Prefer the consented draft and confirmation tools for V1.1.

### `register_custom_food(user_id, food)` / `list_custom_foods(user_id)`

Require explicit per-100g package-label energy, protein, fat, and carbohydrate. Scope foods to that pseudonymous user. If fiber is absent, state that zero means “not counted,” not confirmed absence.

### `record_weight(user_id, weight_kg, measured_at?)` / `get_weight_trend(user_id, limit=28)`

Record measurements without promising an outcome. The current implementation marks calibration readiness after 14 observations; it does not automatically change targets.

### `delete_user_data(user_id)`

Call only after explicit confirmation. Report whether any record was deleted.
