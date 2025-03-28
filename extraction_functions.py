import json
import re
import openai
import streamlit as st

# プロンプト設定を外部JSONファイルから読み込む
with open("prompts.json", "r", encoding="utf-8") as f:
    prompts = json.load(f)

CHUNK_SIZE = prompts.get("chunk_size", 500)
OVERLAP = prompts.get("overlap", 100)
MODEL = prompts.get("model", "gpt-3.5-turbo")
MAX_TOKENS_SINGLE = prompts.get("max_tokens_single", 3000)
MAX_TOKENS_PARTIAL = prompts.get("max_tokens_partial", 300)
MAX_TOKENS_FINAL = prompts.get("max_tokens_final", 3000)
TEMPERATURE = prompts.get("temperature", 0.2)

SINGLE_CHUNK_PROMPT = prompts.get("single_chunk_prompt")
FINAL_CHUNK_PROMPT = prompts.get("final_chunk_prompt")
PARTIAL_SUMMARY_PROMPT = prompts.get("partial_summary_prompt")

def split_text_with_overlap(text, chunk_size=CHUNK_SIZE, overlap=OVERLAP):
    """テキストを指定のチャンクサイズとオーバーラップで分割する"""
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = start + chunk_size
        chunks.append(text[start:end])
        start += (chunk_size - overlap)
    return chunks

def _extract_json_from_string(text: str):
    """LLMの出力からJSON部分のみを抽出してパースする"""
    pattern = r"```json\s*(.*?)\s*```"
    match = re.search(pattern, text, flags=re.DOTALL)
    if match:
        code_block = match.group(1).strip()
        try:
            return json.loads(code_block)
        except Exception:
            pass
    try:
        return json.loads(text)
    except Exception as e:
        st.error(f"JSONパース失敗: {e}")
        return _empty_metadata()

def _empty_metadata():
    return {
        "title": "",
        "technical_field": "",
        "background_art": "",
        "prior_art_documents": [],
        "problems_to_be_solved": "",
        "means_for_solving": "",
        "effects": "",
        "brief_description_of_drawings": "",
        "embodiments": "",
        "claims": [],
        "additional_info": {
            "filing_date": "",
            "publication_date": "",
            "registration_date": "",
            "inventors": [],
            "applicants": [],
            "agents": [],
            "priority_info": ""
        },
        "terminologies": {}
    }

def _call_openai_single_chunk_enhanced(chunk_text: str):
    prompt_text = SINGLE_CHUNK_PROMPT.replace("{chunk_text}", chunk_text)
    try:
        response = openai.ChatCompletion.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "あなたは優秀な特許アナリストです。"},
                {"role": "user", "content": prompt_text}
            ],
            max_tokens=MAX_TOKENS_SINGLE,
            temperature=TEMPERATURE
        )
        result_text = response.choices[0].message["content"].strip()
        return _extract_json_from_string(result_text)
    except Exception as e:
        st.error(f"OpenAI APIエラー（シングルチャンク抽出）: {e}")
        return _empty_metadata()

def _call_openai_partial_summary_enhanced(chunk_text: str):
    prompt_text = PARTIAL_SUMMARY_PROMPT + "\n" + "テキスト:\n" + chunk_text
    try:
        response = openai.ChatCompletion.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "あなたは優秀な要約アナリストです。"},
                {"role": "user", "content": prompt_text}
            ],
            max_tokens=MAX_TOKENS_PARTIAL,
            temperature=TEMPERATURE
        )
        return response.choices[0].message["content"].strip()
    except Exception as e:
        st.error(f"OpenAI APIエラー（部分要約抽出）: {e}")
        return ""

def _call_openai_final_metadata_enhanced(combined_text: str):
    prompt_text = FINAL_CHUNK_PROMPT.replace("{combined_text}", combined_text)
    try:
        response = openai.ChatCompletion.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "あなたは優秀な特許アナリストです。"},
                {"role": "user", "content": prompt_text}
            ],
            max_tokens=MAX_TOKENS_FINAL,
            temperature=TEMPERATURE
        )
        result_text = response.choices[0].message["content"].strip()
        return _extract_json_from_string(result_text)
    except Exception as e:
        st.error(f"OpenAI APIエラー（最終メタデータ抽出）: {e}")
        return _empty_metadata()

def call_openai_for_enhanced_metadata(text: str):
    chunks = split_text_with_overlap(text)
    if len(chunks) == 1:
        return _call_openai_single_chunk_enhanced(chunks[0])
    else:
        partial_summaries = []
        for i, chunk in enumerate(chunks):
            with st.spinner(f"チャンク {i+1}/{len(chunks)} を処理中..."):
                summary = _call_openai_partial_summary_enhanced(chunk)
                partial_summaries.append(summary)
        combined_text = "\n".join(partial_summaries)
        return _call_openai_final_metadata_enhanced(combined_text)
