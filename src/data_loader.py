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
    """1食テーブル（外食100件＋自炊90行）を返す。"""
    return pd.read_csv(DATA_DIR / "meals.csv", encoding="utf-8-sig")


@st.cache_data
def load_recipes() -> pd.DataFrame:
    """自炊レシピの材料表（recipe_id, name, ingredient, amount_g, ...）。提案画面の「材料」表示に使う。"""
    return pd.read_csv(DATA_DIR / "recipes.csv", encoding="utf-8-sig", keep_default_na=False)
