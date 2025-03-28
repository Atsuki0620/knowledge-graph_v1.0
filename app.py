import os
import json
import streamlit as st
import openai

from extraction_functions import call_openai_for_enhanced_metadata
from db_utils import load_knowledge_db, save_knowledge_db, update_knowledge_db
from graph_utils import visualize_knowledge_graph

st.title("特許ナレッジDBアップデート & 可視化デモ")

# ユーザーにAPIキーを入力させる
openai_api_key = st.text_input("OpenAI API Key", type="password")
if not openai_api_key:
    st.stop()
openai.api_key = openai_api_key

# ナレッジDBの読み込み
db = load_knowledge_db()

# ファイルアップロード
st.subheader("特許文書ファイルをアップロード")
uploaded_file = st.file_uploader("PDFまたはテキストファイルを選択", type=["pdf", "txt"])

if uploaded_file is not None:
    if uploaded_file.type == "application/pdf":
        try:
            import pdfplumber
            with pdfplumber.open(uploaded_file) as pdf:
                text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        except Exception as e:
            st.error(f"PDF抽出エラー: {e}")
            text = ""
    else:
        text = uploaded_file.read().decode("utf-8")
    
    st.subheader("抽出されたテキスト（先頭部分）")
    st.text_area("テキスト", text[:1000], height=200)
    
    if st.button("メタデータ抽出＆DB更新"):
        with st.spinner("解析中..."):
            metadata = call_openai_for_enhanced_metadata(text)
            st.json(metadata)
            updated_db = update_knowledge_db(db, metadata, text)
            save_knowledge_db(updated_db)
            st.success("ナレッジDB更新完了")

st.subheader("ナレッジDB内容の表示")
if db["documents"]:
    st.text_area("ナレッジDB", json.dumps(db, ensure_ascii=False, indent=2), height=200)

st.subheader("グラフの可視化")
if st.button("グラフ表示"):
    visualize_knowledge_graph(db)
