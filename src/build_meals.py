"""build_meals：recipes.csv などから、最適化の入口 meals.csv を作る。

使い方（src/ から実行する）:
    python build_meals.py
入力  : data/recipes.csv, data/ingredient_price_map.csv, data/prices.csv,
        data/20260327-mxt_kagsei-mext-000029402_02.xlsx（日本食品標準成分表（八訂）増補2023）,
        data/meals_gaishoku.csv（外食100件）, config.py
出力  : data/meals.csv（列は docs/team_rules.md 第2節。末尾に price_approx 列を追加）

計算の考え方
  自炊1食 = レシピ1人前 × 倍率（config.PORTION_GRID）。
  費用 = Σ 使用量(g) × 1gあたりの価格（最新月）× 倍率。cost_yen = base_cost_yen ÷ (1−ロス率)。
  栄養 = Σ 使用量(g) × (1−廃棄率/100) × 100gあたりの値 ÷ 100 × 倍率。
  準備時間 = (調理+片付け) × (1 + PORTION_PREP_COEF × (倍率−1))。
  外食は meals_gaishoku.csv をそのまま使う（倍率1.0、recipe_id = meal_id）。
"""
import re
from pathlib import Path

import openpyxl
import pandas as pd

import config

DATA = Path("../data")
XLSX = DATA / "20260327-mxt_kagsei-mext-000029402_02.xlsx"

# 成分表の「成分識別子」→ meals.csv の列名
NUTRIENT_COLS = {
    "ENERC_KCAL": "kcal", "PROT-": "protein_g", "FAT-": "fat_g", "CHOCDF-": "carb_g",
    "FIB-": "fiber_g", "NACL_EQ": "salt_g", "CA": "calcium_mg", "FE": "iron_mg", "VITC": "vitamin_c_mg",
}
CORE = ["kcal", "protein_g", "fat_g", "carb_g"]                          # 制約に使う栄養（欠けたら止める）
AUX = ["fiber_g", "salt_g", "calcium_mg", "iron_mg", "vitamin_c_mg"]      # 補助の栄養
MEAL_COLS = ["meal_id", "recipe_id", "name", "type", "portion", "base_cost_yen", "cost_yen", "prep_min"] \
    + CORE + AUX + ["exclude_slots", "is_assumed", "price_approx"]


def _squash(s):
    """食品名の空白（全角・半角）をすべて取り除く。recipes.csv と成分表で空白の種類が違うため。"""
    return re.sub(r"\s+", "", str(s).replace("　", " "))


def _to_float(v):
    """成分表のセルを数値にする。Tr（微量）→0、(x)（推定値）→x、-（未測定）・空欄・*→NaN。"""
    if v is None:
        return float("nan")
    s = str(v).strip().replace(",", "")
    if s == "Tr":
        return 0.0
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
    try:
        return float(s)
    except ValueError:
        return float("nan")


def load_food_table(path=XLSX):
    """成分表の「表全体」シートを読み、{空白なしの食品名: 行} の DataFrame を返す。

    列: food_no, refuse_pct, kcal, protein_g, ... （100gあたり。可食部）。未測定は NaN。
    """
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)["表全体"]
    rows = list(ws.iter_rows(values_only=True))
    ids = rows[11]                                                      # 12行目が成分識別子
    pos = {code: ids.index(code) for code in ["REFUSE", *NUTRIENT_COLS]}
    recs = []
    for r in rows[12:]:
        if not r[1] or not r[3]:                                        # 食品番号・食品名がない行は飛ばす
            continue
        # 成分表の食品名は「＜魚介類＞ （さば類） 缶詰 水煮」のように分類の語が前につく。
        # recipes.csv の食材名は分類の語を省いた形なので、省いたキーを2通り作る（A: ＜＞を省く / B: さらに（）も省く）
        tokens = str(r[3]).split("\u3000")
        tok_a = [t for t in tokens if not (t.startswith("＜") and t.endswith("＞"))]
        tok_b = [t for t in tok_a if not (t.startswith("（") and t.endswith("）"))]
        rec = {"food_no": str(r[1]), "key_a": _squash("".join(tok_a)), "key_b": _squash("".join(tok_b)),
               "refuse_pct": _to_float(r[pos["REFUSE"]])}
        for code, col in NUTRIENT_COLS.items():
            rec[col] = _to_float(r[pos[code]])
        recs.append(rec)
    return pd.DataFrame(recs)


def match_foods(ingredients, foods):
    """recipes.csv の食材名を成分表の行に結びつける。キーA→キーBの順に探し、1件に決まらなければ止まる。

    戻り値: ingredient を index に、成分表の列（food_no, refuse_pct, kcal ...）を持つ DataFrame。
    """
    rows, problems = {}, []
    for ing in sorted(set(ingredients)):
        k = _squash(ing)
        for col in ("key_a", "key_b"):
            hit = foods[foods[col] == k]
            if len(hit) == 1:
                rows[ing] = hit.iloc[0]
                break
            if len(hit) > 1:                                            # 複数に当たる＝食材名があいまい
                problems.append(f"{ing}: 成分表の {len(hit)} 行に当たる {list(hit['food_no'])}")
                break
        else:
            problems.append(f"{ing}: 成分表に見つからない")
    if problems:
        raise ValueError("成分表との照合に失敗:\n  " + "\n  ".join(problems))
    return pd.DataFrame(rows).T.drop(columns=["key_a", "key_b"])


def yen_per_gram(prices, month):
    """prices.csv から、指定月の {item_id: 1gあたりの円} を作る。unit が空欄の品目は config.UNIT_G_ASSUMED を使う。"""
    p = prices[prices["month"] == month].copy()

    def grams(row):
        m = re.fullmatch(r"(\d+(?:\.\d+)?)(kg|g|個|mL)", str(row["unit"]))
        if not m:                                                       # 単位が空欄・未知
            return float(config.UNIT_G_ASSUMED.get(row["item_id"], "nan"))
        n, u = float(m.group(1)), m.group(2)
        return {"kg": n * 1000, "g": n, "個": n * config.EGG_G_PER_PIECE, "mL": n * config.ML_G_PER_ML}[u]

    p["yen_per_g"] = p["price_yen"] / p.apply(grams, axis=1)
    return p.set_index("item_id")["yen_per_g"]


def build_cooking_meals(recipes, ing_map, prices, foods, month, portions, prep_coef, loss_rate):
    """自炊の meals を作る（レシピ × 倍率）。問題があれば原因を示して止まる（黙って欠損にしない）。"""
    ypg = yen_per_gram(prices, month)
    # 食材ごとに、価格・成分表を結びつける
    d = recipes.merge(ing_map[["ingredient", "item_id", "match_type"]], on="ingredient", how="left")
    d = d.merge(match_foods(d["ingredient"], foods).reset_index(names="ingredient"), on="ingredient", how="left")
    for col in ["refuse_pct", *CORE, *AUX]:
        d[col] = pd.to_numeric(d[col])
    d["yen_per_g"] = d["item_id"].map(ypg)
    # 品目がない食材は、config の仮の価格を使う
    assumed = d["ingredient"].map(config.PRICE_ASSUMED_YEN_PER_G)
    d["price_is_approx"] = d["match_type"].ne("直接") | assumed.notna()
    d["yen_per_g"] = d["yen_per_g"].fillna(assumed)

    # 結びつかなかった食材があれば止める
    bad = sorted(d.loc[d["yen_per_g"].isna(), "ingredient"].unique())
    if bad:
        raise ValueError(f"価格が付かない食材: {bad}")
    bad = sorted(d.loc[d[CORE].isna().any(axis=1), "ingredient"].unique())
    if bad:
        raise ValueError(f"制約に使う栄養（kcal・P・F・C）が未測定の食材: {bad}")

    # 食材ごとの費用と栄養（1人前）。補助の栄養の未測定（NaN）は0として足す（過小評価になりうる）
    edible = d["amount_g"] * (1 - d["refuse_pct"].fillna(0) / 100) / 100
    d["yen"] = d["amount_g"] * d["yen_per_g"]
    for col in CORE + AUX:
        d[col] = edible * d[col].fillna(0)

    # レシピごとに合計
    g = d.groupby("recipe_id", sort=True)
    base = g[["yen", *CORE, *AUX]].sum()
    info = g.agg(name=("name", "first"), cook=("cook_min", "first"), cleanup=("cleanup_min", "first"),
                 exclude_slots=("exclude_slots", "first"), is_assumed=("is_assumed", "max"),
                 price_approx=("price_is_approx", "max"))

    out = []
    for portion in portions:
        t = base.mul(portion)                                           # 費用・栄養は倍率に比例
        m = pd.DataFrame({
            "meal_id": [f"{r}_x{portion:.1f}" for r in base.index],
            "recipe_id": base.index,
            "name": [n if portion == 1.0 else f"{n}（×{portion:.1f}）" for n in info["name"]],
            "type": "自炊", "portion": portion,
            "base_cost_yen": t["yen"].round(1).values,
            "cost_yen": (t["yen"].round(1) / (1 - loss_rate)).round(4).values,
            "prep_min": ((info["cook"] + info["cleanup"]) * (1 + prep_coef * (portion - 1))).round(1).values,
        })
        for col in CORE + AUX:
            m[col] = t[col].round(2).values
        m["exclude_slots"] = info["exclude_slots"].fillna("").values
        m["is_assumed"] = info["is_assumed"].values
        m["price_approx"] = info["price_approx"].values
        out.append(m)
    return pd.concat(out, ignore_index=True)


def build_meals(month=None):
    """自炊（レシピ×倍率）と外食を1つの表にして返す。month を省くと prices.csv の最新月。"""
    recipes = pd.read_csv(DATA / "recipes.csv", keep_default_na=False,
                          dtype={"exclude_slots": str, "note": str})
    recipes["is_assumed"] = recipes["is_assumed"].astype(str).str.lower().eq("true")
    for c in ["amount_g", "cook_min", "cleanup_min"]:
        recipes[c] = pd.to_numeric(recipes[c])
    ing_map = pd.read_csv(DATA / "ingredient_price_map.csv", dtype=str, keep_default_na=False)
    ing_map["item_id"] = ing_map["item_id"].replace("", pd.NA)
    prices = pd.read_csv(DATA / "prices.csv", dtype={"item_id": str})
    month = month or sorted(prices["month"].unique())[-1]
    loss = config.LOSS_RATE if config.LOSS_RATE is not None else 0.0   # 未決の間はロスなし（0%）で作る

    cook = build_cooking_meals(recipes, ing_map, prices, load_food_table(), month,
                               config.PORTION_GRID, config.PORTION_PREP_COEF, loss)

    eat = pd.read_csv(DATA / "meals_gaishoku.csv", dtype={"exclude_slots": str}, keep_default_na=True)
    eat["exclude_slots"] = eat["exclude_slots"].fillna("")
    eat["recipe_id"] = eat["meal_id"]          # 外食は meal_id がそのまま「同じ食事」の判定キー
    eat["portion"] = 1.0
    eat["price_approx"] = False
    eat["is_assumed"] = eat["is_assumed"].astype(str).str.lower().eq("true")
    meals = pd.concat([cook, eat[MEAL_COLS]], ignore_index=True)[MEAL_COLS]
    meals.attrs.update(month=month, loss_rate=loss)
    return meals


if __name__ == "__main__":
    meals = build_meals()
    assert meals["meal_id"].is_unique, "meal_id が重複している"
    meals.to_csv(DATA / "meals.csv", index=False, encoding="utf-8")
    c = meals[meals["type"] == "自炊"]
    print(f"価格の月: {meals.attrs['month']} / ロス率: {meals.attrs['loss_rate']}")
    print(f"meals.csv: {len(meals)}行（自炊 {len(c)} / 外食 {len(meals) - len(c)}）")
