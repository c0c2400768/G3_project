"""自作レシピの検証と、1食テーブル（meals.csv と同じ列）への変換。

画面（pages/4_自作レシピ.py）と、提案・分析（候補への合流）の両方から使う。
Streamlit にも DB にも依存しない関数だけを置く。
"""
from __future__ import annotations

import pandas as pd

SLOTS = ("morning", "lunch", "dinner")
SLOT_LABELS = {"morning": "朝", "lunch": "昼", "dinner": "夜"}

NAME_MAX = 40
DESC_MAX = 500
COST_FLOOR_PUBLIC = 50      # 公開レシピの費用の下限（円）。仮案
CONSISTENCY_TOL = 0.20      # kcal と 4P+9F+4C のずれの許容（割合）。仮案

# 項目ごとの許容範囲（これを外れたら登録できない）。仮案
RANGES = {
    "cost_yen": (1, 3000), "prep_min": (0, 180), "kcal": (50, 2500),
    "protein_g": (0, 300), "fat_g": (0, 300), "carb_g": (0, 500),
    "fiber_g": (0, 100), "salt_g": (0, 50), "calcium_mg": (0, 3000),
    "iron_mg": (0, 100), "vitamin_c_mg": (0, 2000),
}
LABELS = {
    "cost_yen": "費用", "prep_min": "準備時間", "kcal": "エネルギー", "protein_g": "たんぱく質",
    "fat_g": "脂質", "carb_g": "炭水化物", "fiber_g": "食物繊維", "salt_g": "食塩相当量",
    "calcium_mg": "カルシウム", "iron_mg": "鉄", "vitamin_c_mg": "ビタミンC",
}
AUX = ["fiber_g", "salt_g", "calcium_mg", "iron_mg", "vitamin_c_mg"]

MEAL_COLUMNS = [
    "meal_id", "recipe_id", "name", "type", "portion", "base_cost_yen", "cost_yen", "prep_min",
    "kcal", "protein_g", "fat_g", "carb_g", "fiber_g", "salt_g", "calcium_mg", "iron_mg",
    "vitamin_c_mg", "exclude_slots", "is_assumed", "price_approx",
]


def exclude_from_allowed(allowed: list[str]) -> str:
    """食べられる枠 → 食べられない枠（meals.csv の exclude_slots の書式。例 'lunch,dinner'）。"""
    return ",".join(s for s in SLOTS if s not in allowed)


def validate(fields: dict) -> list[str]:
    """登録できない誤りの一覧（空なら問題なし）。fields は DB の列名のdict。"""
    errors = []
    name = (fields.get("name") or "").strip()
    if not 1 <= len(name) <= NAME_MAX:
        errors.append(f"料理名は1〜{NAME_MAX}文字で入力してください。")
    if len(fields.get("description") or "") > DESC_MAX:
        errors.append(f"材料と量は{DESC_MAX}文字までです。")
    for key, (lo, hi) in RANGES.items():
        v = fields.get(key)
        if v is None:
            if key in AUX:
                continue  # 補助栄養は任意
            errors.append(f"{LABELS[key]}を入力してください。")
        elif not lo <= v <= hi:
            errors.append(f"{LABELS[key]}は{lo}〜{hi}の範囲で入力してください。")
    excluded = {s for s in (fields.get("exclude_slots") or "").split(",") if s}
    if excluded >= set(SLOTS):  # 3枠すべて除外 = どこにも出せない
        errors.append("食べる時間帯を1つ以上選んでください。")
    return errors


def consistency_warning(fields: dict) -> str | None:
    """kcal が 4×たんぱく質＋9×脂質＋4×炭水化物 から大きくずれていれば警告文を返す。"""
    try:
        calc = 4 * fields["protein_g"] + 9 * fields["fat_g"] + 4 * fields["carb_g"]
        kcal = fields["kcal"]
    except (KeyError, TypeError):
        return None
    if kcal <= 0:
        return None
    if abs(kcal - calc) / kcal > CONSISTENCY_TOL:
        return (f"エネルギー（{kcal:.0f}kcal）と、たんぱく質・脂質・炭水化物からの計算値"
                f"（約{calc:.0f}kcal）が{CONSISTENCY_TOL:.0%}以上ずれています。入力を見直してください。")
    return None


def publish_blockers(fields: dict) -> list[str]:
    """公開できない理由（他人の提案に混ざるので、登録より厳しくする）。"""
    reasons = []
    if (fields.get("cost_yen") or 0) < COST_FLOOR_PUBLIC:
        reasons.append(f"費用が{COST_FLOOR_PUBLIC}円未満のものは公開できません。")
    warn = consistency_warning(fields)
    if warn:
        reasons.append(warn)
    return reasons


def to_meal_rows(rows: list[dict]) -> pd.DataFrame:
    """自作レシピ（user_recipes の行）を、meals.csv と同じ列の表に変換する。

    - 自炊として扱い、倍率は 1.0 のみ（recipe_id は "U"+id）。
    - 費用は入力値のまま（食材ロス率・調理時間倍率の対象にしない）。
    - 追加列：source("user")、owner(作成者のニックネーム)、ai_estimated。
    """
    if not rows:
        return pd.DataFrame(columns=MEAL_COLUMNS + ["source", "owner", "ai_estimated"])
    out = []
    for r in rows:
        rid = f"U{r['id']}"
        out.append({
            "meal_id": f"{rid}_x1.0", "recipe_id": rid, "name": r["name"], "type": "自炊",
            "portion": 1.0, "base_cost_yen": r["cost_yen"], "cost_yen": r["cost_yen"],
            "prep_min": r["prep_min"], "kcal": r["kcal"], "protein_g": r["protein_g"],
            "fat_g": r["fat_g"], "carb_g": r["carb_g"],
            **{k: r.get(k) for k in AUX},
            "exclude_slots": r.get("exclude_slots") or "", "is_assumed": True, "price_approx": False,
            "source": "user", "owner": r["nickname"], "ai_estimated": bool(r.get("ai_estimated")),
        })
    df = pd.DataFrame(out)
    for col in ("cost_yen", "base_cost_yen", "prep_min", "kcal", "protein_g", "fat_g", "carb_g", *AUX):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
