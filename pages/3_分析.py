"""条件を動かして、外食と自炊の費用・損益分岐を比較する分析ページ。"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="条件別の分析 | 食事判断支援", page_icon="📊", layout="wide")

from src import config, ui  # noqa: E402
from src.data_loader import load_meals  # noqa: E402
from src.optimize import assign_slots, optimize  # noqa: E402

ui.apply_theme()
ui.page_header("条件別の分析", "準備時間や食材ロス率を変え、外食のみの場合と費用・組み合わせを比較します。")

LABELS = {
    "kcal": ("エネルギー", "kcal"),
    "protein_g": ("たんぱく質", "g"),
    "fat_g": ("脂質", "g"),
    "carb_g": ("炭水化物", "g"),
    "fiber_g": ("食物繊維", "g"),
    "salt_g": ("食塩相当量", "g"),
    "calcium_mg": ("カルシウム", "mg"),
    "iron_mg": ("鉄", "mg"),
    "vitamin_c_mg": ("ビタミンC", "mg"),
}


def load_analysis_functions():
    """既存の感度分析 Notebook から関数定義セルだけを読み込む。"""
    path = Path(__file__).resolve().parents[1] / "src" / "sensitivity.ipynb"
    with path.open(encoding="utf-8") as f:
        notebook = json.load(f)
    # Use the application's maintained optimizer module. Notebook helpers also
    # expect names such as json, EPS and optimize in their execution namespace.
    ns = {
        "np": __import__("numpy"), "pd": pd, "go": go, "json": json,
        "config": config, "optimize": optimize, "EPS": 1e-9,
        "EATOUT": "外食", "COOK": "自炊",
    }
    for cell in notebook["cells"]:
        src = "".join(cell.get("source", []))
        if cell["cell_type"] == "code" and any(
            marker in src for marker in (
                "def apply_loss", "def breakeven_curve", "def nutrition_cost_gap",
                "def build_nutrition_target", "def _empty_fig",
            )
        ):
            exec(compile(src, str(path), "exec"), ns)
    return ns


@st.cache_resource
def analysis_functions():
    return load_analysis_functions()


conditions = st.session_state.get("conditions", {})
sex = conditions.get("sex", "male")
activity = conditions.get("activity", "normal")
energy = config.KCAL_TABLE.get(sex, config.KCAL_TABLE["male"]).get(activity, 2600)
budget_default = int(conditions.get("budget", 1500))
prep_default = int(conditions.get("max_prep", 90))
saved_params = st.session_state.get("analysis_params", {})
budget_default = int(saved_params.get("budget", budget_default))
prep_default = int(saved_params.get("prep", prep_default))
_g0, _gs = min(config.PREP_GRID), config.PREP_GRID[1] - config.PREP_GRID[0]
prep_default = _g0 + round((prep_default - _g0) / _gs) * _gs  # 15分刻みに丸める
loss_default = int(round(saved_params.get("loss", config.LOSS_RATE) * 100))

with st.form("analysis_conditions"):
    st.subheader("分析条件")
    c1, c2, c3 = st.columns(3)
    budget_input = c1.number_input("1日の予算（円）", 500, 5000, budget_default, 100, key="analysis_budget")
    prep_input = c2.slider("準備時間の上限（分／日）", min_value=min(config.PREP_GRID), max_value=max(config.PREP_GRID), step=15, value=max(min(prep_default, max(config.PREP_GRID)), min(config.PREP_GRID)), key="analysis_prep")
    loss_input = c3.slider("自炊の食材ロス率", 0, 40, max(0, min(40, loss_default)), 5, format="%d%%", key="analysis_loss") / 100
    st.caption(f"目標エネルギー {energy:,} kcal/日 · 朝昼夕の配分 {config.SLOT_RATIO['morning']:.0%}/{config.SLOT_RATIO['lunch']:.0%}/{config.SLOT_RATIO['dinner']:.0%}。基準はトップページで選んだ条件から引き継いでいます。")
    submitted = st.form_submit_button("確認して分析する", type="primary", use_container_width=True)

if submitted:
    st.session_state["analysis_params"] = {
        "budget": int(budget_input), "prep": int(prep_input), "loss": float(loss_input),
    }
    saved_params = st.session_state["analysis_params"]

if not saved_params:
    st.info("分析条件を設定し、「確認して分析する」を押すと結果を表示します。")
    st.stop()

budget = int(saved_params["budget"])
prep = int(saved_params["prep"])
loss = float(saved_params["loss"])
st.caption(f"表示中の分析条件：予算 {budget:,} 円／日 · 準備時間 {prep} 分／日 · 食材ロス率 {loss:.0%}")

try:
    meals = load_meals()
    required = {
        "meal_id", "name", "type", "cost_yen", "prep_min",
        *config.CONSTRAINT_NUTRIENTS,
    }
    missing = sorted(required - set(meals.columns))
    if missing:
        st.error("分析に必要な列が食事データにありません: " + ", ".join(missing))
        st.stop()
    funcs = analysis_functions()
    meals = funcs["apply_loss"](meals, loss)
    slotted = assign_slots(meals, energy, config.SLOT_RATIO, config.SLOT_TOL)
    nutrition = funcs["build_nutrition_target"](energy, config.ENERGY_RATIO, config.KCAL_PER_G, config.KCAL_TOL)
except FileNotFoundError:
    st.error("食事データまたは分析定義が見つかりません。data/meals.csv と src/sensitivity.ipynb を確認してください。")
    st.stop()
except Exception as exc:
    st.error(f"分析の準備に失敗しました: {exc}")
    st.stop()

try:
    best = optimize(slotted, int(budget), int(prep), nutrition, config.AUX_NUTRIENTS)
    baseline = funcs["eatout_baseline"](slotted, int(budget), nutrition, config.AUX_NUTRIENTS)
    savings = funcs["savings"](best, baseline)
except Exception as exc:
    st.error(f"条件の計算に失敗しました: {exc}")
    st.stop()

st.subheader("この条件での比較")
if best["feasible"]:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("最小コスト", f"{best['total_cost']:,.0f} 円")
    m2.metric("準備時間", f"{best['selected']['prep_min'].sum():,.0f} 分", f"上限 {prep} 分")
    m3.metric("食事の合計", f"{best['totals'].get('kcal', float('nan')):,.0f} kcal", f"目標 {energy:,} kcal")
    m4.metric("外食のみとの差", f"{savings['per_day']:,.0f} 円/日" if savings["feasible"] else "比較できません")
    if not baseline["feasible"]:
        st.info("現在の予算と栄養条件を満たす外食のみの組み合わせがないため、節約額は比較できません。")
    selected = best["selected"].copy()
    selected["食事枠"] = selected["slot"].map({"morning": "朝", "lunch": "昼", "dinner": "夜"})
    selected = selected.rename(columns={"name": "メニュー", "type": "区分", "cost_yen": "費用（円）", "prep_min": "準備時間（分）"})
    show_cols = [c for c in ["食事枠", "区分", "メニュー", "費用（円）", "準備時間（分）"] if c in selected.columns]
    st.dataframe(selected[show_cols], hide_index=True, use_container_width=True)
    adequacy = funcs["nutrition_adequacy"](best["totals"], nutrition, config.AUX_REFERENCE)
    adequacy["項目"] = adequacy["nutrient"].map(lambda x: LABELS.get(x, (x, ""))[0])
    adequacy["単位"] = adequacy["nutrient"].map(lambda x: LABELS.get(x, (x, ""))[1])
    adequacy["合計"] = adequacy.apply(lambda r: "—" if pd.isna(r["total"]) else f"{r['total']:,.1f} {r['単位']}", axis=1)
    adequacy["基準との比較"] = adequacy.apply(lambda r: "基準未設定" if r["status"] == "基準未設定" else ("—" if pd.isna(r["ratio_pct"]) else f"{r['ratio_pct']:.0f}%"), axis=1)
    adequacy["判定"] = adequacy["status"]
    with st.expander("栄養の充足度", expanded=False):
        st.dataframe(adequacy[["項目", "role", "合計", "基準との比較", "判定"]].rename(columns={"role": "位置づけ"}), hide_index=True, use_container_width=True)
else:
    st.warning("この条件では、予算・準備時間・栄養の制約をすべて満たす組み合わせがありません。下のグラフで準備時間を広げた場合を確認できます。")
    reason = best.get("reason") or {}
    empty = reason.get("slot_empty", [])
    if empty:
        st.caption("候補がない食事枠: " + "、".join({"morning": "朝", "lunch": "昼", "dinner": "夜"}.get(x, x) for x in empty))
    else:
        clues = []
        if reason.get("budget") is not None and reason["budget"] > budget:
            clues.append(f"他の条件を保つ場合、予算を約{reason['budget']:,.0f}円以上にすると候補が見つかる可能性があります")
        if reason.get("prep_time") is not None and reason["prep_time"] > prep:
            clues.append(f"他の条件を保つ場合、準備時間を約{reason['prep_time']:,.0f}分以上にすると候補が見つかる可能性があります")
        if reason.get("nutrition"):
            clues.append("予算と時間に合う候補はありますが、栄養条件も同時に満たす組み合わせがありません")
        if reason.get("multiple_constraints"):
            clues.append("複数の条件が同時に影響している可能性があります")
        for clue in clues:
            st.caption("• " + clue)

st.divider()
st.subheader("準備時間と費用の損益分岐")
st.caption("線が下がるほど費用を抑えられます。破線は栄養条件を満たす外食のみの費用です。")
try:
    curve = funcs["breakeven_curve"](slotted, int(budget), config.PREP_GRID, nutrition)
    switches = funcs["switch_points"](curve)
    break_even_fig = funcs["plot_breakeven"](curve, switches)
    break_even_fig.update_xaxes(showgrid=True, gridcolor="#e6e5e1", zeroline=True, zerolinecolor="#b9b7b1")
    break_even_fig.update_yaxes(showgrid=True, gridcolor="#e6e5e1", zeroline=True, zerolinecolor="#b9b7b1")
    st.plotly_chart(break_even_fig, use_container_width=True)
    a, b = st.columns(2)
    first = switches["first_feasible_prep"]
    cross = switches["crossover_prep"]
    a.metric("初めて条件を満たす準備時間", f"{first} 分" if first is not None else "範囲内に解なし")
    b.metric("外食のみより安くなる上限", f"{cross} 分" if cross is not None else "範囲内では該当なし")
except Exception as exc:
    st.warning(f"損益分岐の計算を表示できませんでした: {exc}")

st.subheader("準備時間 × 食材ロス率")
st.caption("色は外食のみと比べた1日あたりの差額です。プラスは節約、マイナスは費用増を示します。灰色は条件を満たす案がないセルです。セルにカーソルを合わせると金額と自炊の食数を確認できます。")
try:
    grid = funcs["loss_prep_grid"](slotted, int(budget), config.PREP_GRID, config.LOSS_GRID, nutrition)
    heatmap_fig = funcs["plot_heatmap"](grid)
    # Each cell is narrow on a laptop screen; put details in the hover tooltip
    # instead of repeating long labels inside every cell.
    for trace in heatmap_fig.data:
        if trace.type == "heatmap":
            trace.text = None
            trace.texttemplate = None
            trace.xgap = 1
            trace.ygap = 1
    heatmap_fig.update_layout(height=460, margin=dict(l=70, r=35, t=30, b=65))
    heatmap_fig.update_xaxes(tickangle=0, automargin=True)
    heatmap_fig.update_yaxes(automargin=True)
    st.plotly_chart(heatmap_fig, use_container_width=True)
except Exception as exc:
    st.warning(f"条件別の比較表を表示できませんでした: {exc}")

with st.expander("分析の前提とデータ"):
    st.markdown(
        "- 最適化は朝・昼・夜の各1食を選び、予算・準備時間・栄養条件を満たす中で費用を最小化します。\n"
        "- 外食のみの基準は、準備時間の上限を適用せずに計算します。\n"
        "- 食材ロス率、準備時間の刻み、栄養許容幅には仮定値が含まれます。補助栄養項目の基準が未設定の場合は判定しません。\n"
        "- データ出典と仮定値はトップページの「出典と仮定値」を参照してください。"
    )
