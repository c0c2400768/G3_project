"""アプリ共通のデータ読み込み（トップ画面の担当）。

meals.csv は起動時に1回だけ読み、st.cache_data で保持する。
各ページは `from src.data_loader import load_meals` で使う。
"""
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@st.cache_data
def load_meals() -> pd.DataFrame:
    """1食テーブル（外食100件＋自炊90行）を返す。自炊は光熱費・買い物時間を含む（列 utility_yen・shop_min）。"""
    meals = pd.read_csv(DATA_DIR / "meals.csv", encoding="utf-8-sig")
    # 栄養が推定値の外食（gaishoku_candidates.csv の is_assumed）。meals.csv の is_assumed は全行 True のため使わない
    g = pd.read_csv(DATA_DIR / "gaishoku_candidates.csv", encoding="utf-8-sig", usecols=["meal_id", "is_assumed"])
    est_ids = set(g.loc[g["is_assumed"].astype(str).str.lower().eq("true"), "meal_id"].str.lower())
    meals["nutri_estimated"] = meals["meal_id"].str.lower().isin(est_ids)
    # 自炊に光熱費と買い物時間を足す（値は config。分析ページでは画面から変えられる）
    from src import config
    from src.optimize import apply_cooking_overhead
    return apply_cooking_overhead(meals, config.UTILITY_YEN_PER_MEAL, config.SHOP_MIN_PER_MEAL)


@st.cache_data
def load_recipes() -> pd.DataFrame:
    """自炊レシピの材料表（recipe_id, name, ingredient, amount_g, ...）。提案画面の「材料」表示に使う。"""
    return pd.read_csv(DATA_DIR / "recipes.csv", encoding="utf-8-sig", keep_default_na=False)
