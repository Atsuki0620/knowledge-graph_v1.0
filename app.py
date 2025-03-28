import streamlit as st
import networkx as nx
from pyvis.network import Network

def create_pyvis_graph():
    """
    PyVisを用いてネットワーク構造を可視化するための
    Networkオブジェクトを作成して返す関数
    """

    # サンプル用ノードとエッジを定義
    # 通常はDBやファイルから取得して使います
    nodes = [
        {"id": "N1", "label": "顧客A", "group": "customer"},
        {"id": "N2", "label": "製品X", "group": "product"},
        {"id": "N3", "label": "プロジェクトP", "group": "project"},
        {"id": "N4", "label": "担当者T", "group": "person"},
    ]

    edges = [
        {"source": "N1", "target": "N2", "label": "購入"},
        {"source": "N1", "target": "N3", "label": "関連"},
        {"source": "N3", "target": "N4", "label": "担当"},
        {"source": "N2", "target": "N4", "label": "問い合わせ"},
    ]

    # PyVisオブジェクトを生成
    net = Network(height="600px", width="100%", directed=False)
    
    # ノードの追加
    for n in nodes:
        net.add_node(
            n["id"],
            label=n["label"],
            title=f"ID: {n['id']}<br>Group: {n['group']}",
            group=n["group"]
        )
    
    # エッジの追加
    for e in edges:
        net.add_edge(
            e["source"],
            e["target"],
            title=e["label"]
        )

    # 物理演算(Force-Directed)を有効にしてレイアウトを自動調整
    net.force_atlas_2based()

    return net

def main():
    st.title("Knowledge Graph Visualization Demo")

    # グラフオブジェクトを生成
    net = create_pyvis_graph()

    # PyVisが生成するHTMLファイルを保存
    net.save_graph("graph.html")

    # HTMLをStreamlitコンポーネントとして読み込み表示
    with open("graph.html", "r", encoding="utf-8") as f:
        html_content = f.read()
        # height, scrolling等は適宜調整
        st.components.v1.html(html_content, height=600, scrolling=True)

if __name__ == "__main__":
    main()
