"""一日の提案：トップで確定した条件で最適化を実行し、結果・栄養の充足度・上位5案を表示する。"""
import json
import math
import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="一日の提案", page_icon="🍚")

from src import config, db, optimize as opt, ui, user_recipes as ur  # noqa: E402
from src.data_loader import load_meals, load_recipes  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UNIT = {"kcal": "kcal", "protein_g": "g", "fat_g": "g", "carb_g": "g", "fiber_g": "g", "salt_g": "g",
        "calcium_mg": "mg", "iron_mg": "mg", "vitamin_c_mg": "mg"}
STATUS_COLOR = {"充足": "#1baf7a", "不足": "#eb6834", "超過": "#e34948"}

ui.apply_theme()
ui.larger_text()
SUBTITLE = "トップで確定した条件から、費用が最小の1日の食事を提案します。"

cond = st.session_state.get("conditions")
if not cond:
    # 例外対応：条件を入力せずにこのページを開いた場合
    ui.page_header("一日の提案", SUBTITLE)
    st.warning("条件が入力されていません。トップで条件を入力して確定してください。")
    st.page_link("app.py", label="トップへ戻る")
    st.stop()

kcal_target = config.KCAL_TABLE[cond["sex"]][cond["activity"]]
target = opt.build_nutrition_target(kcal_target, config.ENERGY_RATIO, config.KCAL_PER_G, config.KCAL_TOL)
SEX_JA = {"male": "男性", "female": "女性"}
ACT_JA = {"low": "低い", "normal": "ふつう", "high": "高い"}
ui.hero_stats("一日の提案", SUBTITLE, [
    ("あなた", f"{SEX_JA[cond['sex']]}・活動量{ACT_JA[cond['activity']]}", False),
    ("目標エネルギー", f"{kcal_target:,} kcal", True),
    ("予算", f"{cond['budget']:,}円", False),
    ("準備時間の上限", f"{cond['max_prep']}分", False),
])

# ---------- 候補（自作レシピ・好き度）の読み込み ----------
user = cond.get("nickname")
recipe_rows = db.load_candidate_recipes(user, cond.get("use_own", False), cond.get("use_public", False)) \
    if (cond.get("use_own") or cond.get("use_public")) else []
likes = db.get_likes(user) if (user and cond.get("lam", 0) > 0) else {}

# 同じ条件・同じ候補・同じ好き度なら、計算し直さずに前の結果を使う
cache_key = json.dumps({
    "cond": cond,
    "recipes": [[r["id"], r["cost_yen"], r["prep_min"], r["kcal"], r["protein_g"], r["fat_g"],
                 r["carb_g"], r["exclude_slots"]] for r in sorted(recipe_rows, key=lambda r: r["id"])],
    "likes": sorted(likes.items()),
}, sort_keys=True, default=str)

cached = st.session_state.get("proposal")
if cached and cached["key"] == cache_key:
    res = cached["res"]
else:
    bar = st.progress(0.0, text="計算を始めます… 0%")

    def _on_progress(frac: float) -> None:
        bar.progress(frac, text=f"最適な組み合わせを探しています… {int(frac * 100)}%")

    meals = load_meals()
    if recipe_rows:
        meals = pd.concat([meals, ur.to_meal_rows(recipe_rows)], ignore_index=True)
    slot = opt.assign_slots(meals, kcal_target, config.SLOT_RATIO, config.SLOT_TOL)
    res = opt.optimize_topn(slot, cond["budget"], cond["max_prep"], target, config.AUX_NUTRIENTS,
                            likes=likes, lam=cond.get("lam", 0), on_progress=_on_progress)
    # 外食だけで同じ条件（予算・準備時間・栄養）を満たす最小コスト。節約額の比較に使う
    if res["feasible"]:
        base = opt.optimize(slot[slot["type"] == "外食"], cond["budget"], cond["max_prep"], target,
                            config.AUX_NUTRIENTS)
        res["eatout_cost"] = float(base["total_cost"]) if base["feasible"] else None
    bar.progress(1.0, text="完了 100%")
    bar.empty()
    st.session_state["proposal"] = {"key": cache_key, "res": res}

if (cond.get("use_own") or cond.get("use_public")) and not recipe_rows:
    st.info("自作レシピを候補に含める設定ですが、読み込めたレシピはありませんでした。")
if cond.get("lam", 0) > 0:
    if likes:
        st.caption(f"好みの重視度 {cond['lam']}：評価額 ＝ 総コスト − {cond['lam']}×(好き度−3の合計)。"
                   "好き度が未登録の食事は「3（普通）」として扱います。")
    else:
        st.info("好き度が未登録のため、好みは反映されていません。")


# ---------- 解なし：緩めるべき項目を示す ----------
def show_reason(reason: dict) -> None:
    st.error("条件を満たす1日の組み合わせが見つかりませんでした。")
    items = []
    if reason.get("slot_empty"):
        names = "・".join(ur.SLOT_LABELS[s] for s in reason["slot_empty"])
        items.append(f"{names}の食事の候補がありません（目標エネルギーの配分に合う食事が0件）。")
    if reason.get("budget") is not None:
        items.append(f"予算を **{math.ceil(reason['budget']):,}円** 以上にすると、解が出ます。")
    if reason.get("prep_time") is not None:
        items.append(f"準備時間の上限を **{math.ceil(reason['prep_time'])}分** 以上にすると、解が出ます。")
    if reason.get("nutrition"):
        items.append("栄養の基準を外せば解が出ます。栄養の基準（目標エネルギーの範囲）が条件を厳しくしています。")
    if reason.get("multiple_constraints"):
        items.append("予算・準備時間・栄養のうち、複数の条件が同時に厳しいため、どれか1つを緩めるだけでは解が出ません。")
    for t in items:
        st.warning(t)


if not res["feasible"]:
    show_reason(res["reason"])
    st.page_link("app.py", label="条件を変更する")
    st.stop()


# ---------- 解あり：案の表示 ----------
def nutrient_name(key: str) -> str:
    return f"{ur.LABELS.get(key, key)}（{UNIT.get(key, '')}）"


MEAL_INFO = load_meals().set_index("meal_id")
RECIPES = load_recipes()


def clean_ingredient(name: str) -> str:
    """成分表の食品名から、分類の［ ］を省いて読みやすくする。"""
    return re.sub(r"\s*［[^］]*］\s*", " ", str(name)).strip()


def show_ingredients(sel: pd.DataFrame) -> None:
    """自炊の食事について、材料と分量（倍率ぶん）、食材費を表示する。"""
    cooked = sel[(sel["type"] == "自炊") & sel["recipe_id"].isin(RECIPES["recipe_id"])]
    if cooked.empty:
        return
    with st.expander("自炊の材料と食材費（概算）"):
        for _, r in cooked.iterrows():
            m = re.search(r"_x([0-9.]+)$", str(r["meal_id"]))
            portion = float(m.group(1)) if m else 1.0
            ing = RECIPES[RECIPES["recipe_id"] == r["recipe_id"]]
            info = MEAL_INFO.loc[r["meal_id"]] if r["meal_id"] in MEAL_INFO.index else None
            title = f"**{ui_slot(r['slot'])}：{r['name']}**"
            if info is not None:
                title += f"　食材費 約{info['base_cost_yen']:,.0f}円（ロス{config.LOSS_RATE:.0%}込み {r['cost_yen']:,.0f}円）"
            st.markdown(title)
            st.dataframe(
                pd.DataFrame({"材料": ing["ingredient"].map(clean_ingredient),
                              "分量(g)": (pd.to_numeric(ing["amount_g"]) * portion).round(1)}),
                hide_index=True,
            )
            if info is not None and bool(info.get("price_approx")):
                st.caption("一部の食材は、近い品目の価格で代用した概算です。")
        st.caption("分量は量の倍率を反映しています。調味料は省いている場合があります。")


def ui_slot(slot: str) -> str:
    return ur.SLOT_LABELS.get(slot, slot)


def show_savings(plan: dict) -> None:
    """外食だけで組んだ場合との差額を、1日・1週間・1か月で示す。"""
    eo = res.get("eatout_cost")
    if eo is None:
        st.info("外食だけでは、同じ条件（予算・準備時間・栄養）を満たす組み合わせがありません。")
        return
    diff = eo - plan["total_cost"]
    word = "安い" if diff >= 0 else "高い"
    ui.section("外食だけの場合との比較", "wallet")
    c1, c2, c3 = st.columns(3)
    c1.metric("外食のみ（1日）", f"{eo:,.0f}円")
    c2.metric(f"1週間（7日）", f"{abs(diff) * 7:,.0f}円", f"{word}", delta_color="normal" if diff >= 0 else "inverse")
    c3.metric(f"1か月（30日）", f"{abs(diff) * 30:,.0f}円", f"{word}", delta_color="normal" if diff >= 0 else "inverse")
    st.caption(
        f"この案は外食のみより1日 {abs(diff):,.0f}円{word}です。自炊の費用はロス率{config.LOSS_RATE:.0%}（仮定）を含み、"
        "外食のみは同じ予算・準備時間・栄養の条件で組んだ最小コストです。毎日同じ案を続けた場合の目安です。"
    )


def show_plan(plan: dict) -> None:
    sel = plan["selected"]
    totals = plan["totals"]

    c1, c2, c3 = st.columns(3)
    c1.metric("総コスト", f"{plan['total_cost']:,.0f}円")
    c2.metric("総準備時間", f"{totals['prep_min']:.0f}分")
    c3.metric("総エネルギー", f"{totals['kcal']:,.0f} kcal", help=f"目標 {kcal_target:,} kcal")

    ui.section("この案の献立", "utensils")
    ui.meal_cards([
        {"slot": ui_slot(r["slot"]), "type": r["type"], "name": r["name"],
         "cost": r["cost_yen"], "prep": r["prep_min"], "kcal": r["kcal"]}
        for _, r in sel.iterrows()
    ])
    show_savings(plan)
    show_ingredients(sel)

    # 自作レシピが含まれる場合：作成者と、栄養がAIの概算であることを示す
    if "owner" in sel.columns:
        for _, r in sel.iterrows():
            if pd.notna(r.get("owner")):
                who = "あなたの" if r["owner"] == user else f"{r['owner']}さんの"
                ai = pd.notna(r.get("ai_estimated")) and bool(r["ai_estimated"])
                st.caption(f"「{r['name']}」は{who}自作レシピです。" + ("栄養はAIの概算を含みます。" if ai else ""))

    # 栄養の充足度
    ad = opt.nutrition_adequacy(totals, target, config.AUX_REFERENCE)
    shown = ad[ad["ratio_pct"].notna()]
    fig = go.Figure(go.Bar(
        x=shown["ratio_pct"], y=[nutrient_name(k) for k in shown["nutrient"]], orientation="h",
        marker_color=[STATUS_COLOR.get(s, "#9aa0a6") for s in shown["status"]],
        text=[f"{v:.0f}%（{s}）" for v, s in zip(shown["ratio_pct"], shown["status"])], textposition="outside",
        hoverinfo="skip",
    ))
    fig.add_vline(x=100, line_dash="dash", line_color="#52514e")
    fig.update_traces(marker_line_width=0, textfont_size=14)
    fig.update_layout(template="simple_white", height=70 + 52 * len(shown), showlegend=False, bargap=0.35,
                      font=dict(size=14), xaxis_title="基準に対する割合（%）", margin=dict(l=10, r=80, t=10, b=40),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_yaxes(autorange="reversed")
    ui.section("栄養の充足度", "heart")
    st.plotly_chart(fig)
    st.caption("基準は、下限（下限がなければ上限）に対する割合です。破線が100%です。")

    detail = pd.DataFrame({
        "栄養": [nutrient_name(k) for k in ad["nutrient"]],
        "合計": ad["total"].map(lambda v: "—" if pd.isna(v) else f"{v:,.1f}"),
        "下限": ad["lower"].map(lambda v: "—" if pd.isna(v) else f"{v:,.1f}"),
        "上限": ad["upper"].map(lambda v: "—" if pd.isna(v) else f"{v:,.1f}"),
        "判定": ad["status"],
    })
    with st.expander("栄養の詳細"):
        st.dataframe(detail, hide_index=True)
        st.caption("補助の栄養は基準が未設定のため、合計だけを表示します。自作レシピに未入力の項目があると「データなし」です。")


plans = res["plans"]
if cond.get("lam", 0) == 0:
    ui.result_banner("最安の組み合わせ", f"{plans[0]['total_cost']:,.0f}", "円 / 日",
                     f"条件を満たす案を安い順に {len(plans)} 案出しました。タブで切り替えて比べられます。")
else:
    ui.result_banner("好みを反映した1位の案", f"{plans[0]['total_cost']:,.0f}", "円 / 日",
                     f"条件を満たす組み合わせを、好みを反映した順に {len(plans)} 案出しました。")
tabs = st.tabs([f"案{n + 1}（{p['total_cost']:,.0f}円）" for n, p in enumerate(plans)])
for tab, plan in zip(tabs, plans):
    with tab:
        show_plan(plan)
st.caption("案は、すでに選んだ案と2食以上違うものだけを並べています。")

with st.expander("出典と仮定値"):
    st.markdown(
        "- 食材価格：e-Stat 小売物価統計（東京都区部・月次）の最新月。一部の食材は近い品目の価格で代用（概算）\n"
        "- 栄養：日本食品標準成分表（八訂）増補2023、日本人の食事摂取基準（2025年版）を加工して作成\n"
        "- 外食：外食チェーンの公開資料による価格・栄養。**準備時間（移動・待ち）は仮定値**\n"
        f"- 自炊：調理・片付け時間とロス率（{config.LOSS_RATE:.0%}）は**仮定値**。量の倍率は1.0・1.3・1.5\n"
        "- 朝・昼・夜の配分は朝0.30・昼0.30・夜0.40（仮定）。基準が未設定の補助栄養は充足度を判定しません\n"
        "- 自作レシピの栄養にはAIの概算を含みます。医療・栄養指導の代わりにはなりません。"
    )

# 好み登録ページ用に、今回提案された食事（recipe_id 単位）を保存する
seen, proposed = set(), []
for plan in plans:
    for _, r in plan["selected"].iterrows():
        if r["recipe_id"] not in seen:
            seen.add(r["recipe_id"])
            proposed.append({"recipe_id": r["recipe_id"], "name": r["name"], "type": r["type"],
                             "owner": r.get("owner") if pd.notna(r.get("owner")) else None})
st.session_state["proposed_meals"] = proposed

# ---------- 画面遷移 ----------
b1, b2 = st.columns(2)
if b1.button("好き度を登録する"):
    like_pages = sorted((ROOT / "pages").glob("*好み*.py"))
    if like_pages:
        st.switch_page(f"pages/{like_pages[0].name}")
    else:
        st.info("好き度の登録ページは、まだ作成されていません。")
if b2.button("条件を変更する"):
    st.switch_page("app.py")
