"""トップ画面：使い方の表示、条件入力、ニックネーム（新規／ログイン／なし）、確定して提案へ。

確定した条件は st.session_state["conditions"] に保存し、提案ページ（pages/1_提案.py）へ移る。
ログイン状態は st.session_state["user"]（ニックネーム。未ログインは None）。
"""
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="学生の食事判断支援アプリ", page_icon="🍚", layout="centered")

from src import config, db  # noqa: E402  （set_page_config は最初に呼ぶ必要がある）
from src.data_loader import load_meals  # noqa: E402

PROPOSAL_PAGE = "pages/1_提案.py"
SEX = {"男性": "male", "女性": "female"}
ACTIVITY = {"低い": "low", "ふつう": "normal", "高い": "high"}
MODES = ["登録なし", "ログイン", "新規登録"]

st.session_state.setdefault("user", None)
prev = st.session_state.get("conditions", {})

# ---------- 見出し・使い方 ----------
st.title("学生の食事判断支援アプリ")
st.write(
    "1日の予算・準備時間・栄養の条件から、外食と自炊を組み合わせた"
    "**費用が最小の1日の食事（朝・昼・夜）** を提案します。"
)
st.caption("使い方：条件を入力して「確定して提案する」を押すと、提案画面で計算します。")

with st.expander("出典と仮定値"):
    st.markdown(
        "- 食材価格：e-Stat 小売物価統計（東京都区部・月次、2025-09〜2026-08）。最新月（2026-08）を使用\n"
        "- 栄養：日本食品成分表（八訂）増補2023、日本人の食事摂取基準（2025年版）\n"
        "- 外食：外食チェーン10社の公開資料による100件の価格・栄養\n"
        "- 自炊：学生の自炊を想定して作成した30品。調理時間・食材ロス率"
        f"（基準{config.LOSS_RATE:.0%}）は**仮定値**\n"
        f"- 朝・昼・夜の配分は {config.SLOT_RATIO['morning']:.0%}・"
        f"{config.SLOT_RATIO['lunch']:.0%}・{config.SLOT_RATIO['dinner']:.0%}（仮定）\n"
        "- 自作レシピの栄養はAIの概算を含みます。医療・栄養指導の代わりにはなりません。"
    )

# ---------- データ読み込み ----------
try:
    meals = load_meals()
except Exception:
    st.error("食事データ（data/meals.csv）を読み込めませんでした。管理者に連絡してください。")
    st.stop()

# ---------- ニックネーム ----------
db_ok = db.is_available()
user = st.session_state["user"]

st.subheader("ニックネーム")
if user:
    c1, c2 = st.columns([3, 1])
    c1.success(f"ログイン中：{user}")
    if c2.button("ログアウト"):
        st.session_state["user"] = None
        st.rerun()
    mode = "ログイン中"
else:
    if not db_ok:
        st.warning("データベースに接続できないため、登録・ログインは使えません。「登録なし」で提案できます。")
    mode = st.radio(
        "利用方法",
        MODES if db_ok else MODES[:1],
        horizontal=True,
        help="ログインすると、好き度と自作レシピを保存できます。登録なしでも提案は使えます。",
    )
    if mode == "新規登録":
        st.caption("パスワードは半角の数字4桁です。忘れた場合は再設定できず、新しいニックネームでの登録になります。")
    st.caption("個人情報（本名・連絡先など）はニックネームに入れないでください。")

# ---------- 条件入力フォーム ----------
logged_in_mode = mode in ("ログイン", "ログイン中")  # 好み・自作レシピを使えるのは既存ユーザーだけ

with st.form("conditions_form"):
    if mode in ("ログイン", "新規登録"):
        nickname = st.text_input("ニックネーム（1〜20文字）", max_chars=db.NICKNAME_MAX)
        pin = st.text_input("パスワード（数字4桁）", type="password", max_chars=4)
        pin2 = st.text_input("パスワード（確認）", type="password", max_chars=4) if mode == "新規登録" else None
        st.divider()

    st.markdown("**条件**")
    c1, c2 = st.columns(2)
    sex_label = c1.radio("性別", list(SEX), horizontal=True, index=list(SEX.values()).index(prev.get("sex", "male")))
    act_label = c2.selectbox(
        "身体活動レベル", list(ACTIVITY), index=list(ACTIVITY.values()).index(prev.get("activity", "normal")),
        help="低い：座位中心／ふつう：通学・軽い運動／高い：立ち仕事や運動習慣が多い（食事摂取基準の区分）",
    )
    budget = st.number_input("1日の予算（円）", min_value=500, max_value=5000, step=100, value=prev.get("budget", 1500))
    max_prep = st.slider(
        "1日の準備時間の上限（分）", min_value=min(config.PREP_GRID), max_value=max(config.PREP_GRID),
        step=15, value=prev.get("max_prep", 90), help="買い物を除く、調理・片付け・外食の受け取りなどの合計の想定時間",
    )
    lam = st.slider(
        "好みの重視度", min_value=0, max_value=200, step=10, value=prev.get("lam", 0),
        disabled=not logged_in_mode,
        help="0 は費用だけで選びます。大きいほど、好き度が高い食事を選びやすくなります（ログイン時のみ）。",
    )
    use_own = st.checkbox(
        "自分の自作レシピを候補に含める", value=prev.get("use_own", False), disabled=not logged_in_mode
    )
    use_public = st.checkbox(
        "他の人が公開した自作レシピも候補に含める", value=prev.get("use_public", False), disabled=not db_ok,
        help="栄養はAIの概算を含みます。提案結果には作成者のニックネームが表示されます。",
    )

    submitted = st.form_submit_button("確定して提案する", type="primary")

# ---------- 確定処理 ----------
if submitted:
    # 1) ニックネームの登録／ログイン
    if mode in ("ログイン", "新規登録"):
        if mode == "新規登録" and pin != pin2:
            st.error("パスワード（確認）が一致しません。")
            st.stop()
        ok, msg = (db.register if mode == "新規登録" else db.login)(nickname, pin)
        if not ok:
            st.error(msg)
            st.stop()
        st.session_state["user"] = db.normalize_nickname(nickname)

    user = st.session_state["user"]

    # 2) 条件を保存（ログインしていない人は、使えない項目を無効にして保存する）
    st.session_state["conditions"] = {
        "sex": SEX[sex_label],
        "activity": ACTIVITY[act_label],
        "budget": int(budget),
        "max_prep": int(max_prep),
        "lam": int(lam) if (user and mode != "新規登録") else 0,
        "use_own": bool(use_own) if user else False,
        "use_public": bool(use_public) and db_ok,
        "nickname": user,
    }

    # 3) 提案ページへ
    if Path(__file__).resolve().parent.joinpath(PROPOSAL_PAGE).exists():
        st.switch_page(PROPOSAL_PAGE)
    else:
        st.success("条件を保存しました。（提案ページは未作成のため、ここで止まります）")
