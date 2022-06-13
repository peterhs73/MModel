from abc import ABCMeta, abstractmethod
import h5py
from functools import partialmethod

from mmodel.utility import (
    model_signature,
    model_returns,
    graph_topological_sort,
    param_counter,
)


class TopologicalHandler(metaclass=ABCMeta):
    """Base class for layered execution following topological generation

    Data instance is used for the execution instead of attributes.
    This makes the pipeline cleaner and better for testing. A data
    instance can be a dictionary, tuple of dictionaries, or file instance.
    The Data instance is discarded after each execution or when an exception
    occurs.
    """

    def __init__(self, graph, extra_returns: list = []):

        self.__signature__ = model_signature(graph)
        self.returns = sorted(model_returns(graph) + extra_returns)
        self.order = graph_topological_sort(graph)
        self.graph = graph

    def __call__(self, **kwargs):
        """Execute graph model by layer"""

        data_instance = self.initiate(**kwargs)

        for node, node_attr in self.order:
            try:
                self.run_node(data_instance, node, node_attr)
            except Exception as e:
                self.raise_node_exception(data_instance, node, node_attr, e)

        return self.finish(data_instance, self.returns)

    @abstractmethod
    def initiate(self, **kwargs):
        """Initiate the execution"""

    @abstractmethod
    def run_node(self, data_instance, node, node_attr):
        """Run individual node"""

    @abstractmethod
    def raise_node_exception(self, data_instance, node, node_attr, e):
        """Raise exception when there is a node failure"""

    @abstractmethod
    def finish(self, data_instance, returns):
        """Finish execution"""


class MemHandler(TopologicalHandler):
    """Default model of mmodel module

    Model execute the graph by layer. For parameters, a counter is used
    to track all value usage. At the end of each layer, the parameter is
    deleted if the counter reaches 0.
    """

    def __init__(self, graph, extra_returns: list = []):
        """Add counter to the object"""
        super().__init__(graph, extra_returns)
        self.counter = param_counter(graph, extra_returns)

    def initiate(self, **kwargs):
        """Initiate the value dictionary"""

        count = self.counter.copy()
        return kwargs, count

    def run_node(self, data_instance, node, node_attr):
        """Run node

        At the end of each node calculation, the counter is updated.
        If the counter value is zero, the value is deleted.
        """
        value_dict, count = data_instance
        parameters = node_attr["sig"].parameters
        kwargs = {key: value_dict[key] for key in parameters}
        func_output = node_attr["func"](**kwargs)

        returns = node_attr["returns"]
        if len(returns) == 1:
            value_dict[returns[0]] = func_output
        else:
            value_dict.update(dict(zip(returns, func_output)))

        for key in parameters:
            count[key] -= 1
            if count[key] == 0:
                del value_dict[key]

    def raise_node_exception(self, data_instance, node, node_attr, e):
        """Raise exception

        Delete intermediate attributes
        """

        raise Exception(f"Exception occurred for node {node, node_attr}") from e

    def finish(self, data_instance, returns):
        """Finish and return values"""
        value_dict = data_instance[0]
        return (
            value_dict[returns[0]]
            if len(returns) == 1
            else tuple(value_dict[rt] for rt in returns)
        )


class PlainHandler(TopologicalHandler):
    """A fast and bare-bone model

    The method stores all intermediate values in memory. The calculation steps
    are very similar to Model.
    """

    def initiate(self, **kwargs):
        """Initiate the value dictionary"""

        return kwargs

    def run_node(self, value_dict, node, node_attr):
        """Run node
        
        Store all values in a dictionary.
        """

        parameters = node_attr["sig"].parameters
        kwargs = {key: value_dict[key] for key in parameters}
        func_output = node_attr["func"](**kwargs)

        returns = node_attr["returns"]
        if len(returns) == 1:
            value_dict[returns[0]] = func_output
        else:
            value_dict.update(dict(zip(returns, func_output)))

    def raise_node_exception(self, value_dict, node, node_attr, e):
        """Raise exception

        Delete intermediate attributes
        """

        raise Exception(f"Exception occurred for node {node, node_attr}") from e

    def finish(self, value_dict, returns):
        """Finish and return values"""
        return (
            value_dict[returns[0]]
            if len(returns) == 1
            else tuple(value_dict[rt] for rt in returns)
        )


class H5Handler(TopologicalHandler):
    """Model that stores all data in h5 file

    Each entry of the h5 file is unique, with the instance id, instance name
    and execution number
    """

    def __init__(self, graph, h5_filename: str, extra_returns: list = []):

        # check if file exist
        # write id attribute
        self.h5_filename = h5_filename
        self.exe_count = 0
        self.info = f"H5Handler({h5_filename})"

        super().__init__(graph, extra_returns)

    def initiate(self, **kwargs):
        """Initiate dictionary value"""
        self.exe_count += 1

        f = h5py.File(self.h5_filename, "a")

        exe_group_name = f"{id(self)}_{self.exe_count}"
        exe_group = f.create_group(exe_group_name)

        # write input dictionary to
        self.write(kwargs, exe_group)

        return f, exe_group

    def run_node(self, data_instance, node, node_attr):
        """Run node"""

        exe_group = data_instance[1]

        parameters = node_attr["sig"].parameters
        kwargs = {key: self.read(key, exe_group) for key in parameters}

        func_output = node_attr["func"](**kwargs)

        returns = node_attr["returns"]
        if len(returns) == 1:
            self.write({returns[0]: func_output}, exe_group)
        else:
            self.write(dict(zip(returns, func_output)), exe_group)

    def finish(self, data_instance, returns):
        """output parameters based on returns"""

        f, exe_group = data_instance

        if len(returns) == 1:
            rt = self.read(returns[0], exe_group)
        else:
            rt = tuple(self.read(rt, exe_group) for rt in returns)

        f.close()

        return rt

    def raise_node_exception(self, data_instance, node, node_attr, e):
        """Raise exception when exception occurred for a specific node

        The error message is written as a "_node" attribute to the current group.
        """
        f, exe_group = data_instance
        msg = f"{type(e).__name__} occurred for node {node, node_attr}: {e}"
        exe_group.attrs["note"] = msg
        f.close()

        raise Exception(f"Exception occurred for node {node, node_attr}") from e

    @staticmethod
    def write(value_dict, group):
        """Write h5 dataset/attribute by group

        :param dict value_dict: dictionary of values to write
        :param h5py.group group: open h5py group object
        """

        for k, v in value_dict.items():
            group.create_dataset(k, data=v)

    @staticmethod
    def read(key, group):
        """Read dataset/attribute by group

        :param str key: value name
        :param h5py.group group: open h5py group object
        """

        return group[key][()]
