import inspect
import networkx as nx


def param_sorter(parameter):
    """Sorter for argument parameter

    The values in the tuple are compared in sequential order
    1. Order by parameter kind
    2. Default parameter rank at the end of its kind
    3. Alphabetical order

    :param inspect.Parameter parameter: parameter object
    :rtype: (bool, parameter.name, parameter.kind)
    """

    if parameter.default is not parameter.empty:
        return parameter.kind, True, parameter.name
    else:
        return parameter.kind, False, parameter.name


def model_signature(graph):
    """Obtain the signature from the model graph

    :param DiGraph graph: networkx.Digraph() object,
        with 'func_signature', 'returns' defined for nodes
        and "parameters" for edges.
        The args are a dictionary of inspected signature
    """

    parameters = {}
    for sig in nx.get_node_attributes(graph, "sig").values():
        for pname, param in sig.parameters.items():
            if pname in parameters and param_sorter(
                parameters[pname]
            ) >= param_sorter(param):
                continue
            parameters[pname] = param

    for returns in nx.get_node_attributes(graph, "returns").values():
        for rt in returns:
            parameters.pop(rt, None)  # if doesn't exist return None

    return inspect.Signature(sorted(parameters.values(), key=param_sorter))


def model_returns(graph):
    """Obtain the return parameter from the model graph

    The assumption is that all return parameter names are unique.
    """

    returns = []

    for node in graph.nodes():
        if graph.out_degree(node) == 0:
            returns.extend(graph.nodes[node]["returns"])

    returns.sort()
    return returns


def replace_signature(signature, replacement_dict):
    """Replace signature with a dictionary of (key, pair)

    The function is used to replace several input parameters with an object.
    The signature is the original signature.
    The dictionary key should be the replacement object, and the values
    should be a list of the target parameters to be replaced.
    """

    params = dict(signature.parameters)
    for func, target_list in replacement_dict.items():
        for target in target_list:
            del params[target]
        params[func] = inspect.Parameter(func, 1)

    return signature.replace(parameters=sorted(params.values(), key=param_sorter))


def graph_topological_sort(graph):
    """Determine the topological order

    `nx.topological_generations` outputs a generator with each node list generation.
    However, it does not carry the node attributes. The method
    outputs a list of nodes for each generation.

    :return: topological order of the graph. Returns a list of nodes and its
        attribute
    :rtype: list

    """

    return [(node, graph.nodes[node]) for node in nx.topological_sort(graph)]


def param_counter(graph, extra_returns):
    """Count the number of times a parameter is used for graph execution

    Count all function signature parameters. For extra returns,
    add one to each count value.

    :param list extra_returns: the intermediate parameter to return for
        output.

    :return: dictionary with parameter_name: count pair
    :rtype: dict
    """

    value_list = []
    for sig in nx.get_node_attributes(graph, "sig").values():
        value_list.extend(sig.parameters.keys())

    # add the additional parameter to list
    value_list += extra_returns

    count = {}
    for value in value_list:
        count[value] = count.get(value, 0) + 1

    return count


# def loop_signature(signature, parameters):
#     """Change parameter default from scalar to list"""

#     # reset the default to a list
#     sig_param = dict(signature.parameters)
#     for parameter in parameters:
#         _param = sig_param[parameter]
#         if _param.default != inspect.Parameter.empty:
#             sig_param[parameter] = inspect.Parameter(
#                 _param.name, _param.kind, default=[_param.default]
#             )
#     return inspect.Signature(sig_param.values())


def modify_subgraph(
    graph, subgraph, subgraph_name, subgraph_obj, subgraph_returns=None
):
    """Redirect graph based on subgraph

    Find all parent nodes, not in the subgraph but child nodes in the
    subgraph. (All child nodes of subgraph nodes are in the subgraph).
    The edge attribute is passed down to the new edge. Here a new graph is
    created by deep copy the original graph

    :param graph model_graph: model_graph to modify
    :param graph subgraph: subgraph that is being replaced by a node
        subgraph is a view of the original graph
    :param str subgraph_name: name of the subgraph
    """

    graph = graph.deepcopy()

    # since we are not storing subgraph information here
    # and we are not modifying the subgraph, we do not need to copy
    # the subgraph
    # subgraph = subgraph.deepcopy()
    # subgraph.graph = {'name': subgraph_name}

    new_edges = []
    for node in subgraph.nodes():
        new_edges.extend(
            (parent, subgraph_name)
            for parent in graph.predecessors(node)
            if parent not in subgraph
        )

        new_edges.extend(
            (subgraph_name, child)
            for child in graph.successors(node)
            if child not in subgraph
        )

    graph.remove_nodes_from(subgraph.nodes)
    # remove unique edges
    graph.add_edges_from(set(new_edges))

    # subgraph requires to have the returns attribute
    if subgraph_returns is None:
        try:
            subgraph_returns = subgraph_obj.returns
        except AttributeError:
            raise Exception("'subgraph_returns' not defined")

    graph.set_node_object(subgraph_name, func=subgraph_obj, returns=subgraph_returns)
    # add the subgraph attribute to node

    return graph


def modify_node(graph, node, modifiers, node_returns=None):
    """Add modifiers to node

    The result is a new graph with node object modified.
    """

    graph = graph.deepcopy()
    func = graph.nodes[node]["func"]
    returns = node_returns or graph.nodes[node]["returns"]
    graph.set_node_object(node, func=func, returns=returns, modifiers=modifiers)

    return graph


def parse_input(signature, *args, **kwargs):
    """parse argument based on signature and input

    The default value is automatically filled.
    """

    values = signature.bind(*args, **kwargs)
    values.apply_defaults()
    return values.arguments


def is_node_attr_defined(graph, attr: str):
    """Check if all graph nodes have the target attribute defined

    Use ``set`` to ignore the order. Returns true if all nodes have the target
    attribute
    """

    return set(nx.get_node_attributes(graph, attr).keys()) == set(graph.nodes)


def is_edge_attr_defined(graph, attr: str):
    """Check if all graph edges have the target attribute defined

    Use ``set`` to ignore the order. Returns true if all nodes have the target
    attribute
    """

    return set(nx.get_edge_attributes(graph, attr).keys()) == set(graph.edges)
