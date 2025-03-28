import os
import json
import PyPDF2
import openai
import streamlit as st
import networkx as nx
from pyvis.network import Network

# JSONファイル名（ナレッジDBの保存先）
KNOWLEDGE_DB_FILE = "knowledge_db.json"

def load_knowledge_db():
    """保存済みのナレッジDB(JSON)を読み込む"""
    if os.path.exists(KNOWLEDGE_DB_FILE):
        with open(KNOWLEDGE_DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {"documents": [], "graph": {"nodes": [], "edges": []}}

def save_knowledge_db(db):
    """ナレッジDBをJSON形式で保存"""
    with open(KNOWLEDGE_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def extract_text_from_pdf(pdf_file) -> str:
    """PDFファイルからテキストを抽出するサンプル関数"""
    reader = PyPDF2.PdfReader(pdf_file)
    text_list = []
    for page in reader.pages:
        text_list.append(page.extract_text() or "")
    return "\n".join(text_list)

def call_openai_for_metadata(text: str):
    """
    OpenAI APIを使用して、テキストからメタデータ・要約・キーワードなどを抽出する例。
    実際にはプロンプトを工夫して情報抽出を行う。
    """
    prompt = f"""
あなたは特許文書の要約と主要なキーワード、関連エンティティを抽出するアシスタントです。
以下の特許文書テキストから、(1) 要約、(2) 主要キーワード、(3) 重要な関係性（発明者、対象分野など）を簡潔に抽出し、
JSON形式で出力してください。

テキスト:
{text}
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # 必要に応じて gpt-4 に変更
            messages=[
                {"role": "system", "content": "あなたは優秀な特許アナリストです。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        result_text = response.choices[0].message["content"].strip()
        # OpenAIからの出力をJSONパースする想定
        # 例: {"summary": "...", "keywords": [...], "entities": {...}}
        metadata = json.loads(result_text)  
        return metadata
    except Exception as e:
        st.error(f"OpenAI APIエラー: {e}")
        return None

def update_knowledge_db(db, metadata, original_text):
    """
    既存のナレッジDB(db)に新たな特許文書の情報を追加し、グラフ構造も更新
    metadata: {"summary": "...", "keywords": [...], "entities": {...}}
    original_text: 特許全文
    """
    # 1. 文書IDを発行（簡易）
    doc_id = f"doc_{len(db['documents'])+1}"

    # 2. documents配列に追加
    doc_entry = {
        "id": doc_id,
        "summary": metadata.get("summary", ""),
        "keywords": metadata.get("keywords", []),
        "entities": metadata.get("entities", {}),
        "fulltext": original_text
    }
    db["documents"].append(doc_entry)

    # 3. グラフ（nodes/edges）の更新例
    #    - ここではドキュメントのIDとキーワードを結ぶ簡易的なモデル
    keywords = metadata.get("keywords", [])

    # docノードが未存在なら追加
    if doc_id not in [n["id"] for n in db["graph"]["nodes"]]:
        db["graph"]["nodes"].append({
            "id": doc_id, "label": doc_id, "group": "document"
        })

    # キーワードをノード化
    for kw in keywords:
        if kw not in [n["id"] for n in db["graph"]["nodes"]]:
            db["graph"]["nodes"].append({
                "id": kw, "label": kw, "group": "keyword"
            })
        db["graph"]["edges"].append({
            "source": doc_id,
            "target": kw,
            "label": "has_keyword"
        })

    return db

def visualize_knowledge_graph(db):
    """PyVisでナレッジDBのグラフを描画する"""
    nodes = db["graph"]["nodes"]
    edges = db["graph"]["edges"]

    net = Network(height="600px", width="100%", directed=False)

    # ノード追加
    for n in nodes:
        net.add_node(
            n["id"],
            label=n["label"],
            title=f"{n['id']} (group: {n['group']})",
            group=n["group"]
        )

    # エッジ追加
    for e in edges:
        net.add_edge(
            e["source"],
            e["target"],
            title=e["label"]
        )

    # 物理演算によるレイアウト
    net.force_atlas_2based()
    net.save_graph("graph.html")

    # 作成したHTMLをStreamlitで描画
    with open("graph.html", "r", encoding="utf-8") as f:
        html_content = f.read()
        st.components.v1.html(html_content, height=600, scrolling=True)
