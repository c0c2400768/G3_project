"""自作レシピ：登録・一覧・公開切り替え・削除。栄養は手入力、またはGeminiで概算して確認・修正する。"""
import streamlit as st

st.set_page_config(page_title="自作レシピ", page_icon="🍳", layout="wide")

from src import db, gemini, ui, user_recipes as ur  # noqa: E402

ui.apply_theme()
ui.page_header("自作レシピ", "自分のレシピを登録して、提案の候補に加えられます。")

user = st.session_state.get("user")
if not user:
    st.warning("自作レシピの登録はログインが必要です。トップでログインしてください。")
    st.page_link("app.py", label="トップへ")
    st.stop()
if not db.is_available():
    st.warning("データベースに接続できないため、自作レシピは使えません。")
    st.page_link("app.py", label="トップへ")
    st.stop()

st.caption(f"ログイン中：{user}")

# 入力欄の key（session_state で値を直接入れるため、固定の名前をつける）
NUTRIENT_FIELDS = ["kcal", "protein_g", "fat_g", "carb_g", "fiber_g", "salt_g", "calcium_mg", "iron_mg", "vitamin_c_mg"]

# 直前の「AI概算」の結果は、入力欄を作る前に反映する（作った後の欄は書き換えられないため）
pending = st.session_state.pop("pending_estimate", None)
if pending:
    for k, v in pending.items():
        st.session_state[f"f_{k}"] = v
    st.session_state["ai_estimated"] = True

# ---------- 登録フォーム ----------
st.subheader("レシピを登録する（1食分）")
st.caption("栄養は自分で調べた値を入力するか、AIで概算できます。")
if gemini.is_available():
    st.caption("⚠ AI概算では、入力した料理名と材料・量が Google の Gemini API（無料枠）に送られ、"
               "製品改善に使われる可能性があります。個人情報は入れないでください。")
else:
    st.caption("AI概算は現在使えません。栄養は手入力してください。")
_diag = gemini.last_log_text()
if _diag:
    st.caption(f"直前のAI概算：{_diag}")
if st.session_state.pop("recipe_registered", False):
    st.success("登録しました。")

with st.form("add_recipe"):
    name = st.text_input(f"料理名（{ur.NAME_MAX}文字まで）", max_chars=ur.NAME_MAX, key="f_name")
    description = st.text_area(f"材料と量（{ur.DESC_MAX}文字まで）", max_chars=ur.DESC_MAX, key="f_description",
                               placeholder="例：卵2個、ごはん200g、しょう油小さじ1")
    c1, c2 = st.columns(2)
    cost = c1.number_input("費用（円/1食）", min_value=0.0, max_value=float(ur.RANGES["cost_yen"][1]),
                           step=10.0, value=None, key="f_cost_yen")
    prep = c2.number_input("準備時間（分）", min_value=0.0, max_value=float(ur.RANGES["prep_min"][1]),
                           step=5.0, value=None, key="f_prep_min")
    allowed = st.multiselect("食べる時間帯", list(ur.SLOTS), default=list(ur.SLOTS),
                             format_func=ur.SLOT_LABELS.get)

    st.markdown("**栄養（1食分）**")
    if st.session_state.get("ai_estimated"):
        st.warning("AIの概算が入っています。実際の値と異なることがあるため、確認・修正してから登録してください。")
    n1, n2 = st.columns(2)
    kcal = n1.number_input("エネルギー（kcal）", min_value=0.0, step=10.0, value=None, key="f_kcal")
    protein = n2.number_input("たんぱく質（g）", min_value=0.0, step=1.0, value=None, key="f_protein_g")
    n3, n4 = st.columns(2)
    fat = n3.number_input("脂質（g）", min_value=0.0, step=1.0, value=None, key="f_fat_g")
    carb = n4.number_input("炭水化物（g）", min_value=0.0, step=1.0, value=None, key="f_carb_g")
    with st.expander("補助栄養（任意）"):
        a1, a2 = st.columns(2)
        fiber = a1.number_input("食物繊維（g）", min_value=0.0, step=0.5, value=None, key="f_fiber_g")
        salt = a2.number_input("食塩相当量（g）", min_value=0.0, step=0.5, value=None, key="f_salt_g")
        a3, a4 = st.columns(2)
        calcium = a3.number_input("カルシウム（mg）", min_value=0.0, step=10.0, value=None, key="f_calcium_mg")
        iron = a4.number_input("鉄（mg）", min_value=0.0, step=0.5, value=None, key="f_iron_mg")
        vit_c = st.number_input("ビタミンC（mg）", min_value=0.0, step=5.0, value=None, key="f_vitamin_c_mg")

    make_public = st.checkbox("公開する（他の人の提案の候補に入ります）", value=False)
    b1, b2 = st.columns(2)
    estimate_clicked = b1.form_submit_button(
        f"栄養をAIで概算する（残り{gemini.calls_left()}回）", disabled=not gemini.is_available(),
    )
    submitted = b2.form_submit_button("登録する", type="primary")

# ---------- AI概算 ----------
if estimate_clicked:
    bar = st.progress(0.0, text="AIに送信しています… 0%")

    def _on_progress(frac: float) -> None:
        bar.progress(frac, text=f"AIが概算しています… 約{int(frac * 100)}%（目安）")

    result, msg = gemini.estimate_nutrition(name, description, on_progress=_on_progress)
    if result is None:
        bar.empty()
        st.error(msg)
    else:
        bar.progress(1.0, text="完了 100%")
        st.session_state["pending_estimate"] = result
        st.rerun()  # 次の実行の先頭で、結果を入力欄に反映する

# ---------- 登録 ----------
if submitted:
    fields = {
        "name": name.strip(), "description": description, "cost_yen": cost, "prep_min": prep,
        "kcal": kcal, "protein_g": protein, "fat_g": fat, "carb_g": carb,
        "fiber_g": fiber, "salt_g": salt, "calcium_mg": calcium, "iron_mg": iron, "vitamin_c_mg": vit_c,
        "exclude_slots": ur.exclude_from_allowed(allowed),
        "ai_estimated": bool(st.session_state.get("ai_estimated")), "is_public": make_public,
    }
    errors = ur.validate(fields)
    warn = ur.consistency_warning(fields) if not errors else None
    blockers = ur.publish_blockers(fields) if (make_public and not errors) else []
    if errors:
        for e in errors:
            st.error(e)
    elif blockers:
        for b in blockers:
            st.error(b)
        st.info("公開しない設定にするか、値を直してから登録してください。")
    else:
        if warn:
            st.warning(warn + "（非公開として登録します）")
            fields["is_public"] = False
        ok, msg = db.add_recipe(user, fields)
        if ok:
            # 入力欄を空に戻す（作成後の欄は直接書き換えられないが、削除はできる）
            for key in ("f_name", "f_description", "f_cost_yen", "f_prep_min",
                        *[f"f_{k}" for k in NUTRIENT_FIELDS]):
                st.session_state.pop(key, None)
            st.session_state.pop("ai_estimated", None)
            st.session_state["recipe_registered"] = True
            st.rerun()
        else:
            st.error(msg)

# ---------- 一覧・操作 ----------
st.subheader("登録済みのレシピ")
mine = db.list_my_recipes(user)
if mine is None:
    st.error("レシピ一覧を取得できませんでした。しばらくしてからやり直してください。")
    st.stop()
if not mine:
    st.info("まだ登録がありません。")
    st.stop()

table = [{
    "料理名": r["name"], "公開": "公開" if r["is_public"] else "非公開", "AI概算": "あり" if r["ai_estimated"] else "",
    "費用(円)": r["cost_yen"], "準備(分)": r["prep_min"], "kcal": r["kcal"],
    "P(g)": r["protein_g"], "F(g)": r["fat_g"], "C(g)": r["carb_g"],
    "食べる時間帯": "・".join(ur.SLOT_LABELS[s] for s in ur.SLOTS if s not in (r["exclude_slots"] or "").split(",")),
} for r in mine]
st.dataframe(table, hide_index=True)

by_id = {r["id"]: r for r in mine}
chosen = st.selectbox("操作するレシピ", list(by_id), format_func=lambda i: by_id[i]["name"])
target = by_id[chosen]
c1, c2 = st.columns(2)

if target["is_public"]:
    if c1.button("非公開にする"):
        if db.set_recipe_public(user, chosen, False):
            st.rerun()
        else:
            st.error("更新できませんでした。")
else:
    if c1.button("公開する"):
        blockers = ur.publish_blockers(target)
        if blockers:
            for b in blockers:
                st.error(b)
        elif db.set_recipe_public(user, chosen, True):
            st.rerun()
        else:
            st.error("更新できませんでした。")

@st.dialog("このレシピを削除しますか？")
def confirm_delete(recipe_id, recipe_name: str) -> None:
    """削除の確認ダイアログ。「削除する」を押すまで、何も消えない。"""
    st.write(f"「{recipe_name}」を削除します。この操作は元に戻せません。")
    d1, d2 = st.columns(2)
    if d1.button("キャンセル", width="stretch"):
        st.rerun()
    if d2.button("削除する", type="primary", width="stretch"):
        if db.delete_recipe(user, recipe_id):
            st.rerun()
        else:
            st.error("削除できませんでした。")


if c2.button("このレシピを削除", icon=":material/delete:"):
    confirm_delete(chosen, target["name"])
