import streamlit as st
import openai

from knowledge_utils import (
    load_knowledge_db,
    save_knowledge_db,
    extract_text_from_pdf,
    call_openai_for_metadata,
    update_knowledge_db,
    visualize_knowledge_graph
)

def main():
    st.title("特許ナレッジDBアップデート & 可視化デモ")

    # 0. アプリ開始直後にOpenAI APIキーを入力させる
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    if not openai_api_key:
        st.info("Please add your OpenAI API key to continue.", icon="🗝️")
        st.stop()
    
    # OpenAI APIキーをセット
    openai.api_key = openai_api_key

    # 1. ナレッジDBを読込み
    db = load_knowledge_db()

    # 2. ファイルアップロード
    st.subheader("1. 特許文書ファイルをアップロード")
    uploaded_file = st.file_uploader("PDFファイルを選択", type=["pdf"])

    if uploaded_file is not None:
        # PDFからテキスト抽出
        text = extract_text_from_pdf(uploaded_file)

        # === ここから追加: 抽出したテキストを表示する ===
        st.subheader("アップロードされたPDFの抽出テキスト")
        # テキスト量が多い可能性があるため、text_areaを使うのが便利
        st.text_area("PDFから抽出されたテキスト", text, height=200)
        # === ここまで追加 ===

        # 解析ボタン
        if st.button("2. OpenAI APIで解析し、ナレッジDBを更新"):
            with st.spinner("OpenAI APIで解析中..."):
                metadata = call_openai_for_metadata(text)
                if metadata:
                    st.success("メタデータ抽出成功!")
                    st.json(metadata)

                    # DB更新
                    updated_db = update_knowledge_db(db, metadata, text)
                    save_knowledge_db(updated_db)
                    st.success("ナレッジDBを更新し、JSONファイルに保存しました。")

                    # メモリ上のdbを更新
                    db = updated_db

    st.subheader("3. ナレッジDBの内容を表示")
    if db["documents"]:
        st.write(f"現在のドキュメント数: {len(db['documents'])}")
        if st.checkbox("ナレッジDB(JSON)の中身を表示する"):
            st.json(db)

    st.subheader("4. グラフ構造の可視化")
    if st.button("グラフを表示"):
        visualize_knowledge_graph(db)

if __name__ == "__main__":
    main()
