# WeChat Nutrition Tools V1.2 contracts

## General contract

- Pass a stable pseudonymous `user_id` and reuse a stable `source_message_id` for retry-safe writes.
- Treat saved database records as the source for daily totals, targets, and remaining values.
- Prefer catalog and package-label numbers. Application channels may persist validated model estimates with `data_status: estimated` when lookup fails.
- Surface material `unresolved`, `warnings`, `data_status`, and `notes`.

## Food resolution and calculation

### `lookup_food(query, limit=5)`

Search the controlled catalog when identity is ambiguous. Prefer exact canonical matches and controlled representative entries. Check raw/cooked state and notes.

### `parse_meal(text, user_id?)`

Pass only the exact meal span when a message contains multiple intents. One source mention may resolve to at most one catalog item. If lookup fails, the application may call its model-estimation path before calculation.

### `calculate_meal(items, user_id?)`

Each item requires one controlled or persisted-estimate `food_id` or name plus positive grams. Use for preview without persistence. Never present a `partial` result as a complete meal.

### `save_meal(user_id, items, eaten_at?, note?, source_message_id?)`

Save only fully resolved items. Reuse `source_message_id` if the channel retries delivery. The response includes the Asia/Shanghai meal period.

### `register_custom_food(user_id, food)` / `list_custom_foods(user_id)`

Require explicit per-100g package-label energy, protein, fat, and carbohydrate. Never infer an absent value. A missing fiber value means “not counted,” not confirmed zero.

## Exercise

### `record_exercise(user_id, exercise, exercised_at?, source_message_id?)`

Pass only `type`, `duration_minutes`, `intensity`, `body_parts`, `exercises`, and `steps`. The strict schema rejects extra fields, including model-generated energy. The service estimates expenditure deterministically from controlled MET rules and a saved profile weight when available, then writes the session idempotently.

### `get_daily_exercise(user_id, day?)`

Return saved sessions and deterministic estimates. Do not subtract exercise expenditure from intake or increase the food target automatically.

## Profile and targets

### `get_onboarding_status(user_id)` / `begin_onboarding(user_id)`

Check status first. `begin_onboarding` records consent, so call it only after explicit agreement to the stated data use.

### `record_profile_input(user_id, updates)` / `confirm_profile(user_id)`

Merge only explicit values into the draft. Show the full profile and confirm only after explicit user approval. Confirmation derives targets deterministically.

### `calculate_energy_targets(profile)`

Preview only. Requires a complete adult profile and returns the formula version, REE, PAL, maintenance estimate, product goal adjustment, macros, assumptions, and warnings.

### `upsert_profile(user_id, profile)`

Compatibility tool only. Prefer the consented draft and confirmation workflow.

## Saved-record reports

### `get_daily_balance(user_id, day?)`

Use saved meals only. Interpret `remaining` only when confirmed targets exist; missing targets are not zero targets.

### `get_nutrient_gap(user_id, start_date, end_date)`

Check `days_with_records`; missing days can make averages appear low.

### `generate_weekly_review(user_id, week_start?)`

Summarize recorded behavior, not unobserved intake. Do not diagnose deficiency from food logs.

### `record_weight(user_id, weight_kg, measured_at?)` / `get_weight_trend(user_id, limit=28)`

Record observations without promising outcomes. Fourteen observations mark only technical readiness for review; targets do not change automatically.

### `delete_user_data(user_id)`

Call only after explicit confirmation and report whether anything was deleted.
