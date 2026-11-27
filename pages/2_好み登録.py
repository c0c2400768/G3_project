"""好き度の登録：提案ページで出た食事に★1〜5をつけ、Supabase の likes テーブルに保存する。

- 提案ページ（pages/1_提案.py）が st.session_state["proposed_meals"] に入れた食事を表示する。
- ログイン中のニックネーム（st.session_state["user"]）で保存する。ここでニックネームは入力させない。
- 星を押した時点で、その食事の好き度を保存する（保存ボタンはない）。評価済みの食事も、星を押し直せば変更できる。
- 保存した好き度は、トップの「好みの重視度」を上げたときに、提案の順位へ反映される。
"""
import pandas as pd
import streamlit as st

st.set_page_config(page_title="好き度の登録", page_icon="🍚", layout="wide")

from src import db, ui  # noqa: E402
from src.data_loader import load_meals  # noqa: E402

ui.apply_theme()
ui.likes_css()
ui.page_header("好き度の登録", "食事を評価して、あなた好みの献立に近づけましょう。", icon="heart")

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

# ---------- 表示する食事（recipe_id 単位）。費用は meals.csv の1人前（倍率1.0）から引く ----------
meals = load_meals()
cost_by_id = (
    meals[meals["portion"] == 1.0].drop_duplicates("recipe_id").set_index("recipe_id")["cost_yen"]
)
rows = pd.DataFrame(proposed).drop_duplicates("recipe_id")
rows["cost"] = rows["recipe_id"].map(cost_by_id)

# 登録済みの好き度 {recipe_id: 1〜5}。最初の1回だけ DB から読み、あとは星を押すたびに更新する
CACHE = f"likes_cache_{user}"
if CACHE not in st.session_state:
    st.session_state[CACHE] = db.get_likes(user)
saved: dict[str, int] = st.session_state[CACHE]


def _star_key(rid: str) -> str:
    return f"like_{user}_{rid}"


def on_star(rid: str) -> None:
    """星が押されたら、その食事の好き度を保存する。"""
    key = _star_key(rid)
    picked = st.session_state.get(key)
    cache = st.session_state[CACHE]
    if picked is None:  # 同じ星をもう一度押して外した場合。保存済みの値は消さずに元へ戻す
        if rid in cache:
            st.session_state[key] = cache[rid] - 1
        return
    score = int(picked) + 1  # 0〜4 → 1〜5
    ok, msg = db.save_likes(user, {rid: score})
    if ok:
        cache[rid] = score
        st.toast(f"保存しました（{ui.LIKE_LABELS[score]}）", icon=":material/check_circle:")
    else:
        st.toast(msg, icon=":material/error:")


# ---------- 進捗 ----------
meal_list = [r for _, r in rows.iterrows()]
done = sum(1 for r in meal_list if str(r["recipe_id"]) in saved)
ui.likes_progress(done, len(meal_list))

# ---------- 料理一覧（絞り込み） ----------
head_l, head_r = st.columns([3, 2], vertical_alignment="center")
head_l.markdown('<div class="lk-title">料理一覧</div>', unsafe_allow_html=True)
view = head_r.pills("絞り込み", ["すべて", "未評価", "評価済み"], default="すべて", key="likes_view",
                    label_visibility="collapsed") or "すべて"

if view == "未評価":
    shown = [r for r in meal_list if str(r["recipe_id"]) not in saved]
elif view == "評価済み":
    shown = [r for r in meal_list if str(r["recipe_id"]) in saved]
else:
    shown = meal_list

if not shown:
    st.info("未評価の食事はありません。" if view == "未評価" else "評価済みの食事はまだありません。")

for i in range(0, len(shown), 2):
    cols = st.columns(2)
    for col, meal in zip(cols, shown[i:i + 2]):
        rid = str(meal["recipe_id"])
        score = saved.get(rid)
        owner = meal.get("owner")
        who = f" / {owner}さんの自作" if isinstance(owner, str) and owner else ""
        cost = "自作レシピ" if pd.isna(meal["cost"]) else f"{meal['cost']:,.0f}円"
        with col, st.container(border=True):
            ui.like_card_head(meal["name"], str(meal["type"]), cost + who, done=score is not None)
            st.divider()
            key = _star_key(rid)
            if score is not None:
                st.session_state.setdefault(key, score - 1)  # 登録済みなら、その星を最初から表示する
            st.feedback("stars", key=key, on_change=on_star, args=(rid,))
            ui.like_label(score)

st.caption("★1：好まない　★2：あまり好きではない　★3：普通　★4：好き　★5：とても好き。星を押すとすぐ保存されます。"
           "評価済みの食事も、星を押し直せば変更できます。")
st.caption("星をつけなかった食事は保存されません（未評価は「3（普通）」として扱われます）。"
           "好き度は、トップの「好みの重視度」を0より大きくしたときに、提案の順位へ反映されます。")
b1, b2 = st.columns(2)
b1.page_link("pages/1_提案.py", label="提案ページへ戻る")
b2.page_link("app.py", label="トップへ")
