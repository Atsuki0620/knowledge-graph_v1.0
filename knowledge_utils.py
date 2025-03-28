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

def split_text_with_overlap(text, chunk_size=3000, overlap=200):
    """
    textを chunk_size 文字ずつに分割し、各チャンクを overlap 文字だけ重複させる。

    例:
      chunk_size=3000, overlap=200 の場合、
      1つ目チャンク: text[0 : 3000]
      2つ目チャンク: text[2800 : 5800]
      3つ目チャンク: text[5600 : 8600]
      ...
    """
    chunks = []
    start = 0
    n = len(text)

    while start < n:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        
        # 次チャンクは (chunk_size - overlap) 進めた位置から
        start += (chunk_size - overlap)

        if start >= n:
            break

    return chunks

def call_openai_for_metadata(text: str):
    """
    長文テキストを複数チャンクに分割し、それぞれを要約→最終的に統合したメタデータ(JSON)を返す。
    ここではシンプルに (1)部分要約の文字列のリスト → (2)最終JSON の流れを実装。
    """

    # 1) チャンク分割（3000文字単位、200文字オーバーラップ）
    chunks = split_text_with_overlap(text, chunk_size=3000, overlap=200)

    # もしテキストが短くてチャンクが1つだけなら、そのまま1回の呼び出しでOK
    if len(chunks) == 1:
        return _call_openai_single_chunk(chunks[0])
    else:
        # 2) 各チャンクを部分要約 → partial_summaries に格納
        partial_summaries = []
        for i, chunk in enumerate(chunks):
            with st.spinner(f"チャンク {i+1}/{len(chunks)} を要約中..."):
                summary_text = _call_openai_partial_summary(chunk)
                partial_summaries.append(summary_text)

        # 3) 部分要約を結合し、最終的なメタデータ(JSON)を生成
        #    ここでは「部分要約をつなげて再要約」→ 「再要約した結果をJSON化」 という二段階
        combined_text = "\n".join(partial_summaries)

        final_metadata = _call_openai_final_metadata(combined_text)
        return final_metadata


def _call_openai_partial_summary(chunk_text: str):
    """
    チャンクごとに「短い要約テキスト」を生成する。
    JSONでなく、単なる要約文を返す想定。
    """
    prompt_for_chunk = f"""
以下のテキストを簡潔に200文字以内で要約してください。

テキスト:
{chunk_text}
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "あなたは優秀な要約アシスタントです。"},
                {"role": "user", "content": prompt_for_chunk}
            ],
            max_tokens=500,
            temperature=0.2
        )
        summary = response.choices[0].message["content"].strip()
        return summary
    except Exception as e:
        st.error(f"OpenAI APIエラー（部分要約）: {e}")
        return ""

def _call_openai_final_metadata(combined_text: str):
    """
    部分要約を全部つなげた combined_text から、
    (1) 要約 (2) キーワード (3) 関係エンティティ
    を含む JSON を生成する。
    """
    prompt_for_final = f"""
以下は複数チャンクを部分要約したテキストをつなげたものです。
これを参考に、
(1) 全体の要約
(2) 主なキーワード (箇条書き)
(3) 関係エンティティ (発明者や対象分野など)
を JSON 形式で出力してください。

combined_text:
{combined_text}
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "あなたは優秀な特許文書のアナリストです。"},
                {"role": "user", "content": prompt_for_final}
            ],
            max_tokens=1000,
            temperature=0.2
        )
        result_text = response.choices[0].message["content"].strip()
        # 期待する形式: {"summary": "...", "keywords": [...], "entities": {...}}
        metadata = json.loads(result_text)
        return metadata
    except Exception as e:
        st.error(f"OpenAI APIエラー（最終メタデータ）: {e}")
        # 失敗時は最低限の構造だけ返す
        return {"summary": "", "keywords": [], "entities": {}}


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
