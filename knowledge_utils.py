import os
import json
import re
# PyPDF2の代わりにpdfplumberを使う
import pdfplumber  
import openai
import streamlit as st
import networkx as nx
from pyvis.network import Network

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
    """
    pdfplumberを使ってPDFファイルからテキストを抽出する関数。
    文字化けが多い場合はPyPDF2より安定して読めることが多い。
    """
    text_list = []
    # pdf_file は Streamlitのfile_uploader等のFile-likeオブジェクト
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            # extract_text() でそのページの文字をすべて取得
            page_text = page.extract_text()
            if page_text:
                text_list.append(page_text)
    return "\n".join(text_list)

# 以下、以降の関数は従来のまま据え置き
# call_openai_for_metadata, update_knowledge_db, visualize_knowledge_graph など
# ...

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
    (前回のコードに対して、厳格なJSON生成・デバッグ表示・フォールバック処理を追加)
    """

    # 1) チャンク分割（3000文字単位、200文字オーバーラップ）
    chunks = split_text_with_overlap(text, chunk_size=3000, overlap=200)

    # テキストが短くチャンクが1つだけなら1回のリクエストで完了
    if len(chunks) == 1:
        return _call_openai_single_chunk(chunks[0])
    else:
        # 複数チャンク: (1)部分要約 → (2)再要約(JSON化)
        partial_summaries = []
        for i, chunk in enumerate(chunks):
            with st.spinner(f"チャンク {i+1}/{len(chunks)} を要約中..."):
                summary_text = _call_openai_partial_summary(chunk)
                partial_summaries.append(summary_text)

        combined_text = "\n".join(partial_summaries)
        final_metadata = _call_openai_final_metadata(combined_text)
        return final_metadata

def _call_openai_single_chunk(chunk_text: str):
    """
    テキストが3000文字以下のとき、1回で最終的なJSONメタデータを出す。
    (厳密にJSON出力を促し、パース時に失敗したらフォールバック)
    """
    # Markdownコードブロック + JSONフォーマット指示
    prompt_for_final = f"""
以下の特許文書テキストを読み、
(1) 全体の要約
(2) 主なキーワード (箇条書き)
(3) 関係エンティティ (発明者や対象分野など)
を **JSON形式のみ**で返してください。

出力形式は以下に必ず従ってください。それ以外の文章や注釈は一切書かないでください:

\`\`\`json
{{
  "summary": "<string>",
  "keywords": ["<string>", ...],
  "entities": {{"<entity_key>": "<entity_value>", ...}}
}}
\`\`\`

テキスト:
{chunk_text}
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "あなたは優秀な特許アナリストです。"},
                {"role": "user", "content": prompt_for_final}
            ],
            # max_tokensを十分に確保
            max_tokens=2000,
            temperature=0.2
        )
        result_text = response.choices[0].message["content"].strip()

        # デバッグ表示 (モデルからの生文字列を確認)
        st.write("【DEBUG】Single Chunk 生出力:")
        st.write(result_text)

        # JSONパースを試みる
        metadata = _extract_json_from_string(result_text)
        return metadata

    except Exception as e:
        st.error(f"OpenAI APIエラー（single chunk）: {e}")
        return {"summary": "", "keywords": [], "entities": {}}

def _call_openai_partial_summary(chunk_text: str):
    """
    チャンクごとに「短い要約テキスト」を生成する（JSONではなく文字列）。
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
            max_tokens=1000,
            temperature=0.2
        )
        summary = response.choices[0].message["content"].strip()
        return summary
    except Exception as e:
        st.error(f"OpenAI APIエラー（部分要約）: {e}")
        return ""

def _call_openai_final_metadata(combined_text: str):
    """
    部分要約を結合した combined_text から、最終的なメタデータ(JSON)を生成。
    厳格なJSON出力を促し、失敗時はフォールバック処理。
    """
    prompt_for_final = f"""
以下は複数チャンクを部分要約したテキストを結合したものです。
これをもとに、
(1) 全体の要約
(2) 主なキーワード (箇条書き)
(3) 関係エンティティ (発明者、対象分野など)
を **JSON形式のみ**で返してください。絶対に他の文章は出力しないでください。

出力形式:
\`\`\`json
{{
  "summary": "<string>",
  "keywords": ["<string>", ...],
  "entities": {{"<entity_key>": "<entity_value>", ...}}
}}
\`\`\`

テキスト要約一覧:
{combined_text}
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "あなたは優秀な特許アナリストです。"},
                {"role": "user", "content": prompt_for_final}
            ],
            # max_tokensを十分に確保
            max_tokens=2000,
            temperature=0.2
        )
        result_text = response.choices[0].message["content"].strip()

        # デバッグ表示 (モデルからの生文字列を確認)
        st.write("【DEBUG】Final Metadata 生出力:")
        st.write(result_text)

        # JSONパースを試みる
        metadata = _extract_json_from_string(result_text)
        return metadata

    except Exception as e:
        st.error(f"OpenAI APIエラー（最終メタデータ）: {e}")
        # 失敗時は最低限の構造だけ返す
        return {"summary": "", "keywords": [], "entities": {}}

def _extract_json_from_string(text: str):
    """
    モデル出力から、Markdownの```json ...```を切り出してパース。
    フォールバックとして、直接json.loads()も試す。
    """
    # 1) 正規表現で ```json ... ``` 形式を探す
    pattern = r"```json\s*(.*?)\s*```"
    match = re.search(pattern, text, flags=re.DOTALL)
    if match:
        code_block = match.group(1).strip()
        try:
            return json.loads(code_block)
        except Exception:
            pass  # 失敗したら次のフォールバックへ

    # 2) 直接text全体をjson.loadsしてみる
    #    (ユーザーが余計な文章を出さずにそのまま {} を返す場合など)
    try:
        return json.loads(text)
    except Exception as e:
        st.error(f"JSONパース失敗: {e}")
        # 最終的に失敗したら最低限の構造だけ返す
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
