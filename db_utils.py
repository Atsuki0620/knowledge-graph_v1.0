import json
import os

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

def update_knowledge_db(db, metadata, original_text):
    """
    抽出されたメタデータをもとに、ナレッジDBに新たな特許文書の情報を追加する。
    発明の名称を中心ノードとして、各情報（発明者、先行技術文献、用語定義など）を登録する。
    """
    title = metadata.get("title", "")
    if not title:
        title = f"doc_{len(db['documents'])+1}"
    doc_entry = {
        "id": title,
        "title": title,
        "technical_field": metadata.get("technical_field", ""),
        "background_art": metadata.get("background_art", ""),
        "prior_art_documents": metadata.get("prior_art_documents", []),
        "problems_to_be_solved": metadata.get("problems_to_be_solved", ""),
        "means_for_solving": metadata.get("means_for_solving", ""),
        "effects": metadata.get("effects", ""),
        "brief_description_of_drawings": metadata.get("brief_description_of_drawings", ""),
        "embodiments": metadata.get("embodiments", ""),
        "claims": metadata.get("claims", []),
        "additional_info": metadata.get("additional_info", {}),
        "terminologies": metadata.get("terminologies", {}),
        "fulltext": original_text
    }
    db["documents"].append(doc_entry)
    
    # 中心ノードとしてタイトル（発明の名称）を登録
    if title not in [n["id"] for n in db["graph"]["nodes"]]:
        db["graph"]["nodes"].append({
            "id": title,
            "label": title,
            "group": "document"
        })
    
    # 発明者（additional_info内の inventors）のノード追加
    inventors = metadata.get("additional_info", {}).get("inventors", [])
    for inventor in inventors:
        if inventor not in [n["id"] for n in db["graph"]["nodes"]]:
            db["graph"]["nodes"].append({
                "id": inventor,
                "label": inventor,
                "group": "inventor"
            })
        db["graph"]["edges"].append({
            "source": title,
            "target": inventor,
            "label": "HAS_INVENTOR"
        })
    
    # 先行技術文献と請求項をキーワードとして追加
    keywords = metadata.get("prior_art_documents", []) + metadata.get("claims", [])
    for kw in keywords:
        if kw not in [n["id"] for n in db["graph"]["nodes"]]:
            db["graph"]["nodes"].append({
                "id": kw,
                "label": kw,
                "group": "keyword"
            })
        db["graph"]["edges"].append({
            "source": title,
            "target": kw,
            "label": "HAS_KEYWORD"
        })
    
    # 用語定義の追加（terminologies）
    terminologies = metadata.get("terminologies", {})
    for term in terminologies.keys():
        if term not in [n["id"] for n in db["graph"]["nodes"]]:
            db["graph"]["nodes"].append({
                "id": term,
                "label": term,
                "group": "terminology"
            })
        db["graph"]["edges"].append({
            "source": title,
            "target": term,
            "label": "HAS_TERMINOLOGY"
        })
    return db
