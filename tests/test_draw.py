from mmodel.draw import draw_graph, draw_plain_graph, update_settings, DEFAULT_SETTINGS
import networkx as nx


dot_source = """digraph test {
graph [label="test label" labeljust=l labelloc=t ordering=out splines=ortho]
node [shape=box]
add
subtract
multiply
log
poly
add -> subtract
add -> multiply
add -> log
subtract -> poly
multiply -> poly
}"""

plain_dot_source = """digraph test {
graph [label="test label" labeljust=l labelloc=t ordering=out splines=ortho]
node [shape=box]
a [label=a]
b [label=b]
a -> b [xlabel=""]
}"""


def test_update_settings():
    """Test the update_settings function"""

    setttings = update_settings("test label")
    assert setttings["graph_attr"]["label"] == "test label"

    # check default is deepcopied
    assert "label" not in DEFAULT_SETTINGS["graph_attr"]


def test_draw_plain_model(mmodel_G):
    """Test the model without the node detail"""

    dot_graph = draw_plain_graph(mmodel_G, label="test label")
    assert dot_graph.source.replace("\n", "").replace("\t", "") == dot_source.replace(
        "\n", ""
    )


def test_draw_graph(mmodel_G):
    """Test the model with full node and edge detail"""

    dot_graph = draw_graph(mmodel_G, label="test label")
    # test if add function is included
    assert "add\l\naddition(a, b=2)\lreturn c\l" in dot_graph.source


def test_draw_partial_graph():
    """Test draw graph without node object information"""

    G = nx.DiGraph()
    G.add_edge("a", "b")
    G.name = "test"

    dot_graph = draw_graph(G, label="test label")

    assert dot_graph.source.replace("\n", "").replace(
        "\t", ""
    ) == plain_dot_source.replace("\n", "")
