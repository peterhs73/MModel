import inspect
import networkx as nx
from mmodel.draw import draw_graph
from copy import deepcopy


class ModelGraph(nx.DiGraph):

    """Create model graphs

    ModelGraph inherits from `networkx.DiGraph()`, which has all `DiGraph`
    methods.

    The class adds the "type" attribute to the graph attribute. The factory method
    returns a copy of the dictionary. It is equivalent to
    ``{"type": "ModelGraph"}.copy()`` when called.

    The additional graph operations are added:
    - add_grouped_edges and set_node_objects.
    - Method add_grouped_edges, cannot have both edges to be a list.
    - Method set_node_object update nodes with the node callable "func" and returns.
    - The method adds callable signature 'sig' to the node attribute
    """

    graph_attr_dict_factory = {"type": "ModelGraph"}.copy

    def set_node_object(self, node, func, returns, modifiers: list = []):
        """Add or update the functions of existing node

        If the node does not exist, create the node.
        In the end, the edge attributes are re-determined

        Modifiers are applied directly onto the node.
        """

        # if node not in self.nodes:
        #     self.add_node(node)

        node_dict = self.nodes[node]

        # store the base object
        node_dict["base_obj"] = func

        for mod in modifiers:
            func = mod(func)

        sig = inspect.signature(func)
        node_dict.update(
            {"func": func, "sig": sig, "returns": returns, "modifiers": modifiers}
        )
        self.update_graph()

    def set_node_objects_from(self, node_objects: list):
        """Update the functions of existing nodes

        The method is the same as add node object
        """

        for node_obj in node_objects:
            # unzipping works for input with or without modifiers
            self.set_node_object(*node_obj)

    def view_node(self, node: str):
        """view node information

        The node information is kept consistent with the graph information.
        """

        node_dict = self.nodes[node]
        sig_list = [str(param) for param in node_dict["sig"].parameters.values()]
        # if it is not a proper function just print the repr
        # Model class instance has the attr __name__
        base_name = getattr(node_dict["base_obj"], "__name__", repr(callable))
        if mod_str_list := [
            getattr(mod, "info", mod.__name__) for mod in node_dict["modifiers"]
        ]:
            mod_str = ", ".join(mod_str_list)
        else:
            mod_str = "none"

        return "\n".join(
            [
                f"{node} node",
                f"  base callable: {base_name}",
                f"  signature: {', '.join(sig_list)}",
                f"  returns: {', '.join(node_dict['returns'])}",
                f"  modifiers: {mod_str}",
            ]
        )

    def add_grouped_edge(self, u, v):
        """Add linked edge

        For mmodel, a group edge (u, v) allows u or v
        to be a list of nodes. Represents several nodes
        flow into one node or the other way around.
        """

        if isinstance(u, list) and isinstance(v, list):
            raise Exception("only one edge node can be a list")

        # use add edges from to run less update graph
        # currently a compromise
        if isinstance(u, list):
            self.add_edges_from([(_u, v) for _u in u])
        elif isinstance(v, list):
            self.add_edges_from([(u, _v) for _v in v])
        else:  # neither is a list
            self.add_edge(u, v)

    def add_grouped_edges_from(self, group_edges: list):
        """Add edges from grouped values"""

        for u, v in group_edges:
            self.add_grouped_edge(u, v)

    def add_edge(self, u_of_edge, v_of_edge, **attr):
        """Modify add_edge to update the edge attribute in the end"""

        super().add_edge(u_of_edge, v_of_edge, **attr)
        self.update_graph()

    def add_edges_from(self, ebunch_to_add, **attr):
        """Modify add_edges_from to update the edge attributes"""

        super().add_edges_from(ebunch_to_add, **attr)
        self.update_graph()

    def update_graph(self):
        """Update edge attributes based on node objects and edges"""

        for u, v in self.edges:
            u_rts = set(self.nodes[u].get("returns", ()))
            v_sig = self.nodes[v].get("sig", None)

            if v_sig is not None:
                v_params = set(v_sig.parameters.keys())
                self.edges[u, v]["val"] = list(u_rts.intersection(v_params))

    def __str__(self):
        """Output graph information"""
        # default string is the string output of networkx.Graph
        default_str = "".join(
            [
                type(self).__name__,
                f" named {self.name!r}" if self.name else "",
                f" with {self.number_of_nodes()} nodes and {self.number_of_edges()} edges",
            ]
        )
        docstring = self.graph.get("doc", "")

        return f"{default_str.rstrip()}\n\n{docstring}".rstrip()

    def draw(self, method: callable = draw_graph):
        """Draw the graph

        A drawing is provided. Defaults to ``draw_graph``
        """

        return method(self, str(self))

    def deepcopy(self):
        """Deepcopy graph

        The graph.copy method is a shallow copy. Deepcopy creates copy for the
        attributes dictionary.
        `graph.copy<https://networkx.org/documentation/stable/reference/classes
        /generated/networkx.Graph.copy.html>_`

        However, for subgraphs, deepcopy is incredibly inefficient because
        subgraph contains '_graph', which stores the original graph.
        An alternative method is to copy the code from the copy method,
        but use deepcopy for the items.
        """
        # return deepcopy(self)

        G = self.__class__()
        G.graph.update(deepcopy(self.graph))
        G.add_nodes_from((n, deepcopy(d)) for n, d in self._node.items())
        G.add_edges_from(
            (u, v, deepcopy(datadict))
            for u, nbrs in self._adj.items()
            for v, datadict in nbrs.items()
        )

        return G
