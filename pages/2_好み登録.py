"""好き度の登録：提案ページで出た食事に★1〜5をつけ、Supabase の likes テーブルに保存する。

- 提案ページ（pages/1_提案.py）が st.session_state["proposed_meals"] に入れた食事を表示する。
- ログイン中のニックネーム（st.session_state["user"]）で保存する。ここでニックネームは入力させない。
- 保存した好き度は、トップの「好みの重視度」を上げたときに、提案の順位へ反映される。
"""
import pandas as pd
import streamlit as st

st.set_page_config(page_title="好き度の登録", page_icon="🍚")

from src import db, ui  # noqa: E402
from src.data_loader import load_meals  # noqa: E402

ui.apply_theme()
ui.page_header("好き度の登録", "提案された食事に★をつけると、好みを提案に反映できます。")

user = st.session_state.get("user")
if not user:
    st.warning("好き度の登録はログインが必要です。トップでログインしてください。")
    st.page_link("app.py", label="トップへ")
    st.stop()
if not db.is_available():
    st.warning("データベースに接続できないため、好き度は登録できません。")
    st.page_link("app.py", label="トップへ")
    st.stop()

proposed = st.session_state.get("proposed_meals")
if not proposed:
    st.info("登録する食事がありません。先に提案ページで提案を出してください。")
    st.page_link("pages/1_提案.py", label="提案ページへ")
    st.stop()

st.caption(f"ログイン中：{user}")

# ---------- 表示する食事（recipe_id 単位）。費用は meals.csv の1人前（倍率1.0）から引く ----------
meals = load_meals()
cost_by_id = (
    meals[meals["portion"] == 1.0].drop_duplicates("recipe_id").set_index("recipe_id")["cost_yen"]
)
rows = pd.DataFrame(proposed).drop_duplicates("recipe_id")
rows["cost"] = rows["recipe_id"].map(cost_by_id)

saved = db.get_likes(user)  # {recipe_id: 1〜5}。未登録の食事は含まれない

st.caption("★1：好まない　★2：あまり好きではない　★3：普通　★4：好き　★5：とても好き")
st.caption("星をつけなかった食事は保存されません（未登録は「3（普通）」として扱われます）。")

with st.form("likes_form"):
    keys = {}
    for _, meal in rows.iterrows():
        rid = str(meal["recipe_id"])
        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown(f"**{meal['name']}**")
            cost = "自作レシピ" if pd.isna(meal["cost"]) else f"{meal['cost']:,.0f}円"
            owner = meal.get("owner")
            who = f" / {owner}さんの自作" if isinstance(owner, str) and owner else ""
            st.caption(f"{meal['type']} / {cost}{who}")
        with col2:
            # 登録済みなら、その星を最初から表示する（feedback は 0〜4 を返す）
            keys[rid] = f"like_{user}_{rid}"
            st.feedback("stars", key=keys[rid], default=saved[rid] - 1 if rid in saved else None)
        st.divider()
    submitted = st.form_submit_button("好き度を保存する", type="primary")

if submitted:
    scores = {}
    for rid, k in keys.items():
        picked = st.session_state.get(k)
        if picked is not None:
            scores[rid] = int(picked) + 1  # 0〜4 → 1〜5
    if not scores:
        st.warning("星をつけた食事がありません。")
    else:
        ok, msg = db.save_likes(user, scores)
        if ok:
            st.success(f"{len(scores)}件の好き度を保存しました。")
            saved = db.get_likes(user)
        else:
            st.error(msg)

# ---------- 登録済みの確認 ----------
st.subheader("登録済みの好き度")
shown = [(r["name"], saved[str(r["recipe_id"])]) for _, r in rows.iterrows() if str(r["recipe_id"]) in saved]
if shown:
    for name, score in shown:
        st.write(f"{name}：{'★' * score}{'☆' * (5 - score)}（{score}/5）")
else:
    st.info("まだ好き度が登録されていません。")

st.caption("好き度は、トップの「好みの重視度」を0より大きくしたときに、提案の順位へ反映されます。")
b1, b2 = st.columns(2)
b1.page_link("pages/1_提案.py", label="提案ページへ戻る")
b2.page_link("app.py", label="トップへ")
