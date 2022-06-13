import graphviz
from copy import deepcopy

DEFAULT_SETTINGS = {
    "graph_attr": {
        "labelloc": "t",
        "labeljust": "l",
        "splines": "ortho",
        "ordering": "out",
    },
    "node_attr": {"shape": "box"},
}


def update_settings(label: str):
    """Update graphviz settings

    Creates a copy of the default dictionary
    and update the graph label in the graph attribute.
    """

    # copy() is shallow, does not copy the nested dict
    new_settings = deepcopy(DEFAULT_SETTINGS)
    new_settings["graph_attr"].update({"label": label})

    return new_settings


def draw_plain_graph(G, label=""):
    """Draw plain graph

    :param str name: name of the graph
    :param str label: title of the graph

    Plain graph contains the graph label (name + doc)
    Each node only shows the node name
    """

    settings = update_settings(label)
    dot_graph = graphviz.Digraph(name=G.name, **settings)

    for node in G.nodes:
        dot_graph.node(node)

    for u, v in G.edges:
        dot_graph.edge(u, v)

    return dot_graph


def draw_graph(G, label: str = ""):
    """Draw detailed graph

    :param str name: name of the graph
    :param str label: title of the graph

    Each node shows node label (name + signature + returns)
    """

    settings = update_settings(label)

    dot_graph = graphviz.Digraph(name=G.name, **settings)

    for node, ndict in G.nodes(data=True):

        if "func" in ndict:
            label = (
                f"{node}\l\n{ndict['func'].__name__}"
                f"{ndict['sig']}\lreturn {', '.join(ndict['returns'])}\l"
            )
        else:
            label = node
        dot_graph.node(node, label=label)

    for u, v, edict in G.edges(data=True):

        xlabel = ", ".join(edict["val"]) if "val" in edict else ""
        dot_graph.edge(u, v, xlabel=xlabel)

    return dot_graph
