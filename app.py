import os
import json
import streamlit as st
import networkx as nx
from pyvis.network import Network
import openai
import PyPDF2

# JSONファイル名（ナレッジDBの保存先）
KNOWLEDGE_DB_FILE = "knowledge_db.json"

def load_knowledge_db():
    """
    保存済みのナレッジDB(JSON)を読み込む
    無ければ初期構造を返す
    """
    if os.path.exists(KNOWLEDGE_DB_FILE):
        with open(KNOWLEDGE_DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {"documents": [], "graph": {"nodes": [], "edges": []}}

def save_knowledge_db(db):
    """
    ナレッジDBをJSON形式で保存
    """
    with open(KNOWLEDGE_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def extract_text_from_pdf(pdf_file) -> str:
    """
    PDFファイルからテキストを抽出するサンプル関数
    """
    reader = PyPDF2.PdfReader(pdf_file)
    text_pages = []
    for page in reader.pages:
        text_pages.append(page.extract_text() or "")
    return "\n".join(text_pages)

def call_openai_for_metadata(text: str):
    """
    OpenAI APIを使用して、特許文書テキストから
    - (1)要約
    - (2)主要キーワード
    - (3)重要な関係性 (例: 発明者, 対象分野, etc.)
    を抽出する例。
    
    実際にはプロンプト設計を工夫し、出力フォーマットを明確に指示する。
    """
    prompt = f"""
あなたは優秀な特許アナリストです。
以下の特許文書テキストから、以下の情報をJSON形式で抽出してください。

1) "summary": 文章全体の要約
2) "keywords": 主要なキーワードやテクノロジー分野のリスト
3) "entities": 発明者、出願番号、公開日など重要情報をまとめたオブジェクト

特許テキスト:
{text}
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # または "gpt-4"
            messages=[
                {"role": "system", "content": "あなたは特許文書のメタデータを抽出するアシスタントです。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        result_text = response.choices[0].message["content"].strip()

        # JSON形式で返す想定なので、パース
        metadata = json.loads(result_text)
        return metadata

    except Exception as e:
        st.error(f"OpenAI APIエラー: {e}")
        return None

def update_knowledge_db(db, metadata, original_text):
    """
    既存のナレッジDB(db)に新たに特許文書の情報を追加し、
    グラフ(nodes/edges)も更新するサンプル。
    
    metadata: {"summary": "...", "keywords": [...], "entities": {...}}
    original_text: PDFから抽出した全文テキスト
    """
    # 文書IDを適当に発行
    doc_id = f"doc_{len(db['documents'])+1}"

    # ドキュメント情報を追加
    doc_entry = {
        "id": doc_id,
        "summary": metadata.get("summary", ""),
        "keywords": metadata.get("keywords", []),
        "entities": metadata.get("entities", {}),
        "fulltext": original_text
    }
    db["documents"].append(doc_entry)

    # グラフ情報を更新
    # ここでは "doc_id" ノード と "キーワード"ノードを結ぶ簡易例
    if doc_id not in [n["id"] for n in db["graph"]["nodes"]]:
        db["graph"]["nodes"].append({
            "id": doc_id,
            "label": doc_id,
            "group": "document"
        })

    for kw in metadata.get("keywords", []):
        # キーワードノードが未追加なら追加
        if kw not in [n["id"] for n in db["graph"]["nodes"]]:
            db["graph"]["nodes"].append({
                "id": kw,
                "label": kw,
                "group": "keyword"
            })
        # エッジ追加
        db["graph"]["edges"].append({
            "source": doc_id,
            "target": kw,
            "label": "has_keyword"
        })

    return db

def visualize_knowledge_graph(db):
    """
    PyVisを使ってナレッジDB中のノード・エッジを描画する
    """
    net = Network(height="600px", width="100%", directed=False)
    
    # ノード追加
    for n in db["graph"]["nodes"]:
        net.add_node(
            n["id"],
            label=n["label"],
            title=f"{n['id']} (group: {n['group']})",
            group=n["group"]
        )
    
    # エッジ追加
    for e in db["graph"]["edges"]:
        net.add_edge(
            e["source"],
            e["target"],
            title=e["label"]
        )
    
    # レイアウト調整
    net.force_atlas_2based()

    net.save_graph("graph.html")

    # Streamlitに埋め込む
    with open("graph.html", "r", encoding="utf-8") as f:
        html_content = f.read()
        st.components.v1.html(html_content, height=600, scrolling=True)

def main():
    st.title("特許ナレッジDBアップデート & 可視化デモ")

    # ユーザーにAPIキーを入力させる
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    if not openai_api_key:
        st.info("Please enter your OpenAI API key to continue.", icon="🗝️")
        st.stop()

    # 入力されたキーをセット
    openai.api_key = openai_api_key

    # 1. ナレッジDB読込み
    db = load_knowledge_db()

    st.subheader("1. 特許文書(PDF)をアップロード")
    uploaded_file = st.file_uploader("PDFファイルを選択", type=["pdf"])

    if uploaded_file is not None:
        text = extract_text_from_pdf(uploaded_file)
        st.write("ファイルを解析し、テキストを抽出しました。")

        if st.button("2. OpenAI APIで解析し、ナレッジDBを更新"):
            with st.spinner("OpenAI APIでメタデータ抽出中..."):
                metadata = call_openai_for_metadata(text)
                if metadata:
                    st.success("メタデータ抽出成功！")
                    st.json(metadata)  # 抽出結果のプレビュー

                    updated_db = update_knowledge_db(db, metadata, text)
                    save_knowledge_db(updated_db)
                    st.success("ナレッジDBを更新し、JSONファイルに保存しました。")

                    # メモリ上のdbも更新しておく
                    db = updated_db

    st.subheader("3. ナレッジDBの内容を表示")
    st.write(f"現在のドキュメント数: {len(db['documents'])}")
    if st.checkbox("ナレッジDB(JSON)の中身を表示する"):
        st.json(db)

    st.subheader("4. グラフ構造を可視化")
    if st.button("グラフを表示"):
        visualize_knowledge_graph(db)

if __name__ == "__main__":
    main()
