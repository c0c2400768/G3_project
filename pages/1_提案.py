"""【仮】提案ページ。トップ画面から条件を受け取れるかの確認用。
本番は提案担当（高居さん）が、このファイルを丸ごと置き換える。"""
import streamlit as st

st.set_page_config(page_title="一日の提案", page_icon="🍚")
st.title("一日の提案（仮）")

cond = st.session_state.get("conditions")
if not cond:
    # 例外対応：条件を入力せずにこのページを直接開いた場合
    st.warning("条件が入力されていません。トップで条件を入力して確定してください。")
    st.page_link("app.py", label="トップへ戻る")
    st.stop()

st.info("ここに最適化の結果が入ります（未実装）。受け取った条件：")
st.json(cond)
st.page_link("app.py", label="条件を変更する")
