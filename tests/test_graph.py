
import pytest
from inspect import signature
from tests.conftest import graphs_equal
from mmodel import ModelGraph

GRAPH_REPR = """ModelGraph named 'test' with 5 nodes and 5 edges

test object

long description"""


def test_default_mockgraph(mmodel_G, standard_G):
    """Test if default ModelGraph matches the ones created by DiGraph"""

    # assert graph equal
    graphs_equal(mmodel_G, standard_G)

def test_graph_name(mmodel_G):
    """Test naming and docs of the graph"""
    assert mmodel_G.name == "test"

def test_graph_str(mmodel_G):
    """Test graph representation"""


    assert str(mmodel_G) == GRAPH_REPR

def test_update_node_objects():

    def func_a(a, b):
        return None

    def func_b(c, d):
        return None

    G = ModelGraph()
    G.add_edge('node_a', 'node_b')
    G.update_node_object('node_a', func_a, ['c'])
    assert G.nodes['node_a']['rts'] == ['c']
    assert 'sig' in G.nodes['node_a']

    # test the edges are updated
    assert G.edges['node_a', 'node_b'] == {}
    G.update_node_object('node_b', func_b, ['e'])
    assert G.edges['node_a', 'node_b'] == {'val': ['c']}


def test_update_node_objects_from():

    def func_a(a, b):
        return None

    def func_b(c, d):
        return None

    G = ModelGraph()
    G.add_edge('node_a', 'node_b')
    G.update_node_objects_from([('node_a', func_a, ['c']), ('node_b', func_b, ['e'])])

    assert G.edges['node_a', 'node_b'] == {'val': ['c']}


def test_copy(mmodel_G):
    """Test if copy works with MGraph"""

    graphs_equal(mmodel_G.copy(), mmodel_G)


"""The following tests are modified based on networkx.classes.tests"""



def test_graph_chain(mmodel_G):
    """Test Chain graph"""

    G = mmodel_G
    DG = G.to_directed(as_view=True)
    SDG = DG.subgraph(["subtract", "poly"])
    RSDG = SDG.reverse(copy=False)
    assert G is DG._graph
    assert DG is SDG._graph
    assert SDG is RSDG._graph


def test_subgraph(mmodel_G):
    """Test subgraph view"""
    G = mmodel_G

    # full subgraph
    H = G.subgraph(["add", "multiply", "subtract", "poly", "log"])
    graphs_equal(H, G)  # check if they are the same

    # partial subgraph
    H = G.subgraph(["subtract"])
    assert H.adj == {"subtract": {}}
    assert H._graph == G  # original graph

    # partial subgraph
    H = G.subgraph(["subtract", "poly"])
    assert H.adj == {"subtract": {"poly": {'val': ['e']}}, "poly": {}}
    assert H._graph == G  # original graph

    # empty subgraph
    H = G.subgraph([])
    assert H.adj == {}
    assert G.adj != {}
    assert H._graph == G  # original graph


def test_subgraph_copy(mmodel_G):
    """Test the copy of subgraph is no longer a view of original"""

    G = mmodel_G
    H = G.subgraph(["subtract", "poly"]).copy()

    assert H.adj == {"subtract": {"poly": {'val': ['e']}}, "poly": {}}

    H.remove_node("poly")
    assert "poly" in G
    # not exactly sure how to test this
    assert not hasattr(H, "_graph")
