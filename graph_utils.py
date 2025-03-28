from pyvis.network import Network
import streamlit as st

def visualize_knowledge_graph(db):
    """PyVisを使ってナレッジDBのグラフを可視化する"""
    nodes = db["graph"]["nodes"]
    edges = db["graph"]["edges"]
    net = Network(height="600px", width="100%", directed=False)
    for n in nodes:
        net.add_node(n["id"], label=n["label"], title=f"{n['id']} (group: {n['group']})", group=n["group"])
    for e in edges:
        net.add_edge(e["source"], e["target"], title=e["label"])
    net.force_atlas_2based()
    net.save_graph("graph.html")
    with open("graph.html", "r", encoding="utf-8") as f:
        html_content = f.read()
        st.components.v1.html(html_content, height=600, scrolling=True)
