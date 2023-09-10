import streamlit as st
import pandas as pd
import pydeck as pdk

# Sample data: Replace this with your Neo4j query results
nodes = {
    "id": ["Alice", "Bob", "Eve", "Python", "Java"],
    "type": ["Person", "Person", "Person", "Language", "Language"]
}
edges = [
    ("Alice", "Bob", "KNOWS"),
    ("Alice", "Eve", "KNOWS"),
    ("Alice", "Python", "LIKES"),
    ("Bob", "Java", "LIKES")
]

# Convert to DataFrame
nodes_df = pd.DataFrame(nodes)
edges_df = pd.DataFrame(edges, columns=["source", "target", "relationship"])

# Prepare data for pydeck chart
nodes_df["x"] = [0, 1, 2, 3, 4]
nodes_df["y"] = [0, 1, 0, 1, 0]

# Render in Streamlit
st.title("Interactive Knowledge Graph")

# Generate a pydeck chart
edge_chart = pdk.Layer(
    "LineLayer",
    data=edges_df,
    get_source_position="[x, y]",
    get_target_position="[x, y]",
    get_source_position_expr=["[x,y]"],
    get_target_position_expr=["[x,y]"],
    get_width=1,
    get_color=[255, 0, 0]
)

node_chart = pdk.Layer(
    "ScatterplotLayer",
    data=nodes_df,
    get_position="[x, y]",
    get_radius=200,
    get_fill_color=[0, 0, 255]
)

st.pydeck_chart(pdk.Deck(
    layers=[edge_chart, node_chart],
    initial_view_state={
        "latitude": 0,
        "longitude": 0,
        "zoom": 3
    },
    map_style=None
))
