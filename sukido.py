
import streamlit as st
import pandas as pd
from pathlib import Path

# =====================================
# 1. 画面設定
# =====================================

st.set_page_config(
    page_title="好き度登録",
    layout="wide"
)

st.title("🍽️ 好き度登録")

st.write(
    "提案された食事の好き度を登録してください。"
)

# =====================================
# 2. 食事データの読み込み
# =====================================

BASE_DIR = Path(__file__).resolve().parent

@st.cache_data
def load_meals():
    return pd.read_csv(
        BASE_DIR / "data" / "meals.csv"
    )

try:
    meals_df = load_meals()

except FileNotFoundError:
    st.error("data/meals.csv が見つかりません。")
    st.stop()

except Exception:
    st.error("食事データを読み込めませんでした。")
    st.stop()

# 必要な列があるか確認する
required_columns = [
    "recipe_id",
    "name",
    "type",
    "cost_yen"
]

if not all(
    col in meals_df.columns
    for col in required_columns
):
    st.error("meals.csv の列名を確認してください。")
    st.write("現在の列名：", meals_df.columns.tolist())
    st.stop()

# =====================================
# 3. ニックネーム入力
# =====================================

nickname = st.text_input(
    "ニックネームを入力してください",
    max_chars=20
).strip()

if nickname:
    st.caption(f"利用者：{nickname}")

# =====================================
# 4. 提案された食事の取得
# =====================================

# 他の担当者の提案画面から
# データが渡された場合
if "suggested_meals" in st.session_state:

    suggested_df = pd.DataFrame(
        st.session_state["suggested_meals"]
    )

# まだ提案機能が完成していない場合
# meals.csv から動作確認用に3品を取得
else:

    suggested_df = (
        meals_df
        .drop_duplicates(subset="recipe_id")
        .head(3)
        .copy()
    )

    suggested_df["slot"] = [
        "朝食", "昼食", "夕食"
    ][:len(suggested_df)]

    st.info(
        "現在は動作確認用の食事を表示しています。"
    )

if suggested_df.empty:
    st.warning("表示できる食事がありません。")
    st.stop()

# =====================================
# 5. 食事一覧の表示
# =====================================

st.subheader("今回提案された食事")

display_df = suggested_df[
    ["slot", "name", "type", "cost_yen"]
].rename(columns={
    "slot": "時間帯",
    "name": "料理名",
    "type": "外食・自炊",
    "cost_yen": "費用（円）"
})

st.dataframe(
    display_df,
    hide_index=True
)

# =====================================
# 6. 好き度の保存場所
# =====================================

if "likes" not in st.session_state:
    st.session_state["likes"] = {}

saved_likes = st.session_state["likes"].get(
    nickname, {}
)

# =====================================
# 7. 好き度入力
# =====================================

st.subheader("料理の好き度")

st.caption(
    "★1：好まない　"
    "★2：あまり好きではない　"
    "★3：普通　"
    "★4：好き　"
    "★5：とても好き"
)

scores = {}

with st.form("likes_form"):

    for _, meal in suggested_df.iterrows():

        recipe_id = str(meal["recipe_id"])

        col1, col2 = st.columns([3, 2])

        with col1:
            st.markdown(
                f"**{meal['slot']}：{meal['name']}**"
            )

            st.caption(
                f"{meal['type']} / "
                f"{meal['cost_yen']}円"
            )

        with col2:

            # 未登録の好き度は3
            old_score = saved_likes.get(
                recipe_id, 3
            )

            selected = st.feedback(
                "stars",
                default=old_score - 1,
                key=f"{nickname}_{recipe_id}"
            )

            # feedbackは0〜4を返すため
            # 1〜5に変換する
            scores[recipe_id] = (
                3 if selected is None
                else selected + 1
            )

        st.divider()

    submitted = st.form_submit_button(
        "好き度を保存する",
        type="primary"
    )

# =====================================
# 8. 好き度の保存
# =====================================

if submitted:

    if not nickname:

        st.warning(
            "ニックネームを入力してください。"
        )

    else:

        if nickname not in st.session_state["likes"]:
            st.session_state["likes"][nickname] = {}

        st.session_state["likes"][nickname].update(
            scores
        )

        st.success("好き度を保存しました！")

# =====================================
# 9. 登録済み好き度の確認
# =====================================

st.subheader("登録済みの好き度")

saved_likes = st.session_state["likes"].get(
    nickname, {}
)

if saved_likes:

    for _, meal in suggested_df.iterrows():

        recipe_id = str(meal["recipe_id"])

        if recipe_id in saved_likes:

            score = saved_likes[recipe_id]

            st.write(
                f"{meal['name']}："
                f"{'★' * score}{'☆' * (5 - score)}"
                f"（{score}/5）"
            )

else:

    st.info(
        "まだ好き度が登録されていません。"
    )

st.caption(
    "※現在はセッション内への一時保存です。"
    "Supabaseへの接続は今後追加します。"
)
