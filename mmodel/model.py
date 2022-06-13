import inspect
from mmodel.utility import parse_input, is_node_attr_defined, is_edge_attr_defined
from mmodel.draw import draw_graph
import networkx as nx


class Model:
    """Create model executable

    :param object graph: ModelGraph instance (digraph)
    :param class handler: Handler class that handles model execution. By default,
        the handler takes the graph as the first parameter. If additional parameters
        are required, use keyword arguments directly.
    :param list modifiers: modifiers used for the whole graph model executable.
        Optional, defaults to an empty list.
    """

    def __init__(self, graph, handler, modifiers: list = [], **handler_args):

        assert self._is_valid_graph(graph)

        self.__name__ = f"{graph.name} model"

        # store only the copy of the graph, note this is not the same copy
        # used by the handler
        # modify self._graph does not change the model itself
        self._graph = nx.freeze(graph.deepcopy())
        self._modifiers = modifiers
        self._handler = handler

        executor = handler(self._graph, **handler_args)
        self._handler_info = getattr(executor, "info", self._handler.__name__)

        for mdf in modifiers:
            executor = mdf(executor)

        self.__signature__ = executor.__signature__
        self.returns = executor.returns
        self.executor = executor

    def __call__(self, *args, **kwargs):

        # process input
        data_input = parse_input(self.__signature__, *args, **kwargs)

        return self.executor(**data_input)

    def __str__(self):
        """Output callable information"""

        sig_list = [str(param) for param in self.__signature__.parameters.values()]

        if mod_str_list := [
            getattr(mod, "info", mod.__name__) for mod in self._modifiers
        ]:
            mod_str = ", ".join(mod_str_list)
        else:
            mod_str = "none"

        return "\n".join(
            [
                f"{self.__name__}",
                f"  signature: {', '.join(sig_list)}",
                f"  returns: {', '.join(self.returns)}",
                f"  handler: {self._handler_info}",
                f"  modifiers: {mod_str}",
                f"{self._graph.graph.get('doc', '')}",
            ]
        ).rstrip()

    @staticmethod
    def _is_valid_graph(G):
        """Check if model graph is valid to build an executable

        ``mmodel`` does not allow cycle graphs, graphs with isolated nodes,
        and all nodes have callable attributes defined.
        The method is bound to Model class because the features
        are specific to ``Model`` class.
        """

        assert nx.is_directed(G), "invalid graph: undirected graph"
        assert not nx.recursive_simple_cycles(G), "invalid graph: graph contains cycles"
        assert not list(nx.isolates(G)), "invalid graph: graph contains isolated nodes"

        assert is_node_attr_defined(
            G, "func"
        ), "invalid graph: graph contains nodes with undefined callables"

        # the following might occur when the node object is incorrectly constructed
        assert is_node_attr_defined(G, "returns"), (
            "invalid graph: graph contains nodes with undefined callables returns, "
            "recommend using ModelGraph set_node_object method to add node object"
        )
        assert is_node_attr_defined(G, "sig"), (
            "invalid graph: graph contains nodes with undefined callables signatures, "
            "recommend using ModelGraph set_node_object method to add node object"
        )
        assert is_edge_attr_defined(G, "val"), (
            "invalid graph: graph contains edges with undefined variable attributes, "
            "recommend using ModelGraph set_node_object method to add node object"
        )

        return True

    def get_node(self, node):
        """Quick access to node within the model"""

        return self._graph.nodes[node]

    def get_node_object(self, node):
        """Quick access to node callable within the model"""

        return self._graph.nodes[node]["func"]

    def view_node(self, node):
        """View a specific node"""

        return self._graph.view_node(node)

    def draw(self, method: callable = draw_graph):
        """Draw the graph of the model

        A drawing is provided. Defaults to ``draw_graph``
        """

        return method(self._graph, str(self))
