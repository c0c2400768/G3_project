"""トップ画面：条件入力（主役）、入力に合わせた目安、ログイン（右上のポップオーバー）、確定して提案へ。

確定した条件は st.session_state["conditions"] に保存し、提案ページ（pages/1_提案.py）へ移る。
ログイン状態は st.session_state["user"]（ニックネーム。未ログインは None）。
"""
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="学生の食事判断支援アプリ", page_icon="🍚", layout="wide")

from src import config, db, ui  # noqa: E402  （set_page_config は最初に呼ぶ必要がある）
from src.data_loader import load_meals  # noqa: E402
from src.sources import sources_markdown  # noqa: E402

ui.apply_theme()

PROPOSAL_PAGE = "pages/1_提案.py"
SEX = {"男性": "male", "女性": "female"}
ACTIVITY = {"低い": "low", "ふつう": "normal", "高い": "high"}
SLOT_NAMES = {"morning": "朝", "lunch": "昼", "dinner": "夜"}

st.session_state.setdefault("user", None)
prev = st.session_state.get("conditions", {})

# ---------- データ読み込み ----------
try:
    load_meals()
except Exception:
    st.error("食事データ（data/meals.csv）を読み込めませんでした。管理者に連絡してください。")
    st.stop()

db_ok = db.is_available()

# ---------- 右上：ログイン／登録（ポップオーバー） ----------
_, top_right = st.columns([4, 1])
current_user = st.session_state["user"]
with top_right.popover(current_user or "ログイン / 登録", icon=":material/person:", width="stretch"):
    if current_user:
        st.write(f"ログイン中：**{current_user}**")
        st.caption("好き度と自作レシピを保存できます。")
        if st.button("ログアウト", key="logout", width="stretch"):
            st.session_state["user"] = None
            st.rerun()
    elif not db_ok:
        st.warning("データベースに接続できないため、登録・ログインは使えません。ログインなしで提案できます。")
        reason = db.unavailable_reason()
        if reason:
            st.caption(f"原因の候補：{reason}")
    else:
        mode = st.radio("方法", ["ログイン", "新規登録"], horizontal=True, label_visibility="collapsed", key="auth_mode")
        nickname = st.text_input("ニックネーム（1〜20文字）", max_chars=db.NICKNAME_MAX, key="auth_nickname")
        pin = st.text_input("パスワード（数字4桁）", type="password", max_chars=4, key="auth_pin")
        pin2 = ""
        if mode == "新規登録":
            pin2 = st.text_input("パスワード（確認）", type="password", max_chars=4, key="auth_pin2")
            st.caption("忘れた場合は再設定できず、新しいニックネームでの登録になります。")
        st.caption("個人情報（本名・連絡先など）はニックネームに入れないでください。ログインしなくても提案は使えます。")
        if st.button(mode, key="auth_go", type="primary", width="stretch"):
            if mode == "新規登録" and pin != pin2:
                st.toast("パスワード（確認）が一致しません。", icon=":material/error:")
            else:
                ok, msg = (db.register if mode == "新規登録" else db.login)(nickname, pin)
                if ok:
                    st.session_state["user"] = db.normalize_nickname(nickname)
                    st.toast(f"{st.session_state['user']}さんとしてログインしました。", icon=":material/check_circle:")
                    st.rerun()
                else:
                    st.toast(msg, icon=":material/error:")

logged_in = bool(st.session_state["user"])

# ---------- バナー（このアプリで分かること） ----------
ui.hero_stats(
    "今日の1日、外食と自炊をどう組む？",
    "予算・準備時間・栄養の条件から、費用がいちばん安い朝・昼・夜の組み合わせを提案します。",
    [("外食のみ（例）", "1,170円", False, "soup"), ("最適な組み合わせ（例）", "662円", True, "pot"),
     ("1か月の節約（例）", "約15,000円", False, "coins")],
    note="例は、女性・ふつう・予算1,500円・準備時間90分の場合の分析結果です。条件によって変わります。",
)

# ---------- 入力の範囲と刻み ----------
BUDGET_MIN, BUDGET_MAX = 500, 5000
PREP_MIN, PREP_MAX = min(config.PREP_GRID), max(config.PREP_GRID)
BUDGET_STEP = 100
PREP_STEP = config.PREP_GRID[1] - config.PREP_GRID[0]  # 15分。分析ページ・最適化のグリッドと合わせる
SEX_ICON = {"男性": "man", "女性": "woman"}
ACT_ICON = {"低い": "event_seat", "ふつう": "directions_walk", "高い": "directions_run"}


def _clamp(v, lo, hi):
    return max(lo, min(hi, int(v)))


def _snap(v, lo: int, hi: int, step: int) -> int:
    """範囲内に収め、lo から step 刻みの値に丸める（例：47分 → 45分）。"""
    v = _clamp(v, lo, hi)
    return _clamp(lo + round((v - lo) / step) * step, lo, hi)


def _adjust(key: str, delta: int, lo: int, hi: int, step: int) -> None:
    """増減ボタンの処理。範囲を超えず、刻みに乗るようにそろえる。"""
    st.session_state[key] = _snap(st.session_state[key] + delta, lo, hi, step)


def _on_type(key: str, lo: int, hi: int, step: int) -> None:
    """直接入力された値を刻みに丸める。"""
    st.session_state[key] = _snap(st.session_state[key], lo, hi, step)


# 値は session_state に持つ（ボタンで増減するため）。前回確定した条件があればそれを初期値にする
st.session_state.setdefault("budget_v", _snap(prev.get("budget", 1500), BUDGET_MIN, BUDGET_MAX, BUDGET_STEP))
st.session_state.setdefault("prep_v", _snap(prev.get("max_prep", 90), PREP_MIN, PREP_MAX, PREP_STEP))


def stepper(key: str, label: str, icon: str, lo: int, hi: int, step: int,
            dec: list[int], inc: list[int], help: str | None = None) -> int:
    """大きな数値と、減らす／増やすボタンの組。現在の値を返す。"""
    ui.field_label(label, icon, help)
    c_val, c_btn = st.columns([2, 5], vertical_alignment="center")
    with c_val:
        # クリックして直接入力もできる（Enter か枠の外をクリックで確定）。ボタンの増減と同じ値を共有する
        st.number_input(label, min_value=lo, max_value=hi, step=step, format="%d", key=key,
                        label_visibility="collapsed", on_change=_on_type, args=(key, lo, hi, step))
    with c_btn:
        for kind, steps in (("dec", dec), ("inc", inc)):
            with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                ui.step_tag(kind)
                for d in steps:
                    st.button(f"{d:+,}".replace("-", "−"), key=f"{kind}_{key}_{abs(d)}", on_click=_adjust,
                              args=(key, d, lo, hi, step), width="stretch")
    return st.session_state[key]


# ---------- 条件入力と、入力に合わせた目安 ----------
left, right = st.columns([3, 2], gap="medium")

with left:
    with st.container(border=True, key="cond_card"):
        ui.section("あなたの条件", "sliders")
        sex_default = next((k for k, v in SEX.items() if v == prev.get("sex", "male")), "男性")
        act_default = next((k for k, v in ACTIVITY.items() if v == prev.get("activity", "normal")), "ふつう")
        ui.field_label("性別", "user")
        sex_label = st.segmented_control(
            "性別", list(SEX), default=sex_default, key="sex_sel", label_visibility="collapsed", width="stretch",
            format_func=lambda k: f":material/{SEX_ICON[k]}: {k}",
        ) or sex_default
        ui.field_label(
            "身体活動レベル", "activity",
            help="低い：座位中心／ふつう：通学・軽い運動／高い：立ち仕事や運動習慣が多い（食事摂取基準の区分）",
        )
        act_label = st.segmented_control(
            "身体活動レベル", list(ACTIVITY), default=act_default, key="act_sel", label_visibility="collapsed", width="stretch",
            format_func=lambda k: f":material/{ACT_ICON[k]}: {k}",
        ) or act_default
        budget = stepper("budget_v", "1日の予算", "wallet", BUDGET_MIN, BUDGET_MAX, BUDGET_STEP,
                         [-1000, -100], [100, 1000])
        max_prep = stepper("prep_v", "1日の準備時間の上限", "clock", PREP_MIN, PREP_MAX, PREP_STEP,
                           [-30, -15], [15, 30],
                           help="買い物を除く、調理・片付け・外食の受け取りなどの合計の想定時間")
        with st.expander("詳細設定（好み・自作レシピ）", icon=":material/settings:"):
            lam = st.slider(
                "好みの重視度", min_value=0, max_value=200, step=10, value=prev.get("lam", 0),
                disabled=not logged_in,
                help="0 は費用だけで選びます。大きいほど、好き度が高い食事を選びやすくなります（ログイン時のみ）。",
            )
            use_own = st.checkbox("自分の自作レシピを候補に含める", value=prev.get("use_own", False), disabled=not logged_in)
            use_public = st.checkbox(
                "他の人が公開した自作レシピも候補に含める", value=prev.get("use_public", False), disabled=not db_ok,
                help="栄養はAIの概算を含みます。提案結果には作成者のニックネームが表示されます。",
            )
            if not logged_in:
                st.caption("好みと自分の自作レシピは、右上からログインすると使えます。")

with right:
    kcal = config.KCAL_TABLE[SEX[sex_label]][ACTIVITY[act_label]]
    ui.preview_card(
        kcal,
        [(SLOT_NAMES[s], round(kcal * r)) for s, r in config.SLOT_RATIO.items()],
        round(budget / 3),
        "準備時間が短いほど、自炊が選べず費用が上がります。目標エネルギーは食事摂取基準（2025年版）の推定エネルギー必要量です。",
        rich=True,
    )

submitted = st.button("確定して提案する", type="primary", icon=":material/auto_awesome:", width="stretch", key="confirm")

# ---------- 確定処理 ----------
if submitted:
    user = st.session_state["user"]
    st.session_state["conditions"] = {
        "sex": SEX[sex_label],
        "activity": ACTIVITY[act_label],
        "budget": int(budget),
        "max_prep": int(max_prep),
        "lam": int(lam) if user else 0,
        "use_own": bool(use_own) if user else False,
        "use_public": bool(use_public) and db_ok,
        "nickname": user,
    }
    if Path(__file__).resolve().parent.joinpath(PROPOSAL_PAGE).exists():
        st.switch_page(PROPOSAL_PAGE)
    else:
        st.success("条件を保存しました。（提案ページは未作成のため、ここで止まります）")

# ---------- このアプリでできること ----------
st.markdown("")
ui.feature_cards([
    ("list", "上位5案を比べる", "好みも反映できる"),
    ("heart", "栄養の充足度", "基準に対する割合"),
    ("trend", "損益分岐の分析", "前提を動かして確認"),
])

with st.expander("出典と仮定値"):
    st.markdown(sources_markdown())
