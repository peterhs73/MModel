from abc import ABCMeta, abstractmethod
import h5py
from functools import partialmethod

from mmodel.utility import (
    model_signature,
    model_returns,
    graph_topological_sort,
    param_counter,
)


def partial_handler(cls, **kwargs):
    """Partial Handler class given the keyword arguments

    :param class cls: handler class
    :return: class with partial __init__ parameter defined

    The returned class retains the same class name but with modified __init__ method.
    The function is used to modify Handler classes with additional parameter arguments.
    Only keyword arguments are accepted. The resulting class does not complete share
    the properties of the original class. Therefore this is only recommend for modifying
    handler class.
    
    The function is adopted from:
    https://stackoverflow.com/a/58039373/7542501

    The built in ``collection.namedtuple`` has similar implementation:
    https://github.com/python/cpython/blob/
    9081bbd036934ab435291db9d32d02fd42282951/Lib/collections/__init__.py#L501

    A similar implementation is discussed on python issue 77600:
    https://github.com/python/cpython/issues/77600

    The tests for this function is adopted from
    https://github.com/python/cpython/pull/6699
    """

    name = cls.__name__
    class_namespace = {"__init__": partialmethod(cls.__init__, **kwargs)}
    new_cls = type(name, (cls,), class_namespace)

    return new_cls


class TopologicalHandler(metaclass=ABCMeta):
    """Base class for layered execution following topological generation

    Data instance is used for the execution instead of attributes. This makes
    the pipeline cleaner and better testing. A data instance can be a dictionary,
    tuple of dictionaries, or file instance. The Data instance is discarded after
    each execution or when exception occurs.
    """

    def __init__(self, graph, additional_returns: list):

        self.__signature__ = model_signature(graph)
        self.returns = sorted(model_returns(graph) + additional_returns)
        self.order = graph_topological_sort(graph)
        self.graph = graph.copy()

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

    def __init__(self, graph, additional_returns: list):
        """Add counter to the object"""
        super().__init__(graph, additional_returns)
        self.counter = param_counter(graph, additional_returns)

    def initiate(self, **kwargs):
        """Initiate the value dictionary"""

        count = self.counter.copy()
        return kwargs, count

    def run_node(self, data_instance, node, node_attr):
        """Run node

        At end of each node calculation, the counter is updated. If counter is
        zero, the value is deleted.
        """
        value_dict, count = data_instance
        parameters = node_attr["sig"].parameters
        kwargs = {key: value_dict[key] for key in parameters}
        func_output = node_attr["obj"](**kwargs)

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
        if len(returns) == 1:
            return_val = value_dict[returns[0]]
        else:
            return_val = tuple(value_dict[rt] for rt in returns)

        return return_val


class PlainHandler(TopologicalHandler):
    """A fast and bare-bone model

    The method simply store all intermediate values in memory. The calculation steps
    are very similar to Model.
    """

    def initiate(self, **kwargs):
        """Initiate the value dictionary"""

        return kwargs

    def run_node(self, value_dict, node, node_attr):
        """Run node

        At end of each node calculation, the counter is updated. If counter is
        zero, the value is deleted.
        """

        parameters = node_attr["sig"].parameters
        kwargs = {key: value_dict[key] for key in parameters}
        func_output = node_attr["obj"](**kwargs)

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
        if len(returns) == 1:
            return_val = value_dict[returns[0]]
        else:
            return_val = tuple(value_dict[rt] for rt in returns)

        return return_val


class H5Handler(TopologicalHandler):
    """Model that stores all data in h5 file

    Each entry of the h5 file is unique, with the instance id, instance name
    and execution number
    """

    def __init__(self, graph, additional_returns: list, h5_filename: str):

        # check if file exist
        # write id attribute
        self.h5_filename = h5_filename
        self.exe_count = 0

        super().__init__(graph, additional_returns)

    def initiate(self, **kwargs):
        """Initate dictionary value"""
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

        func_output = node_attr["obj"](**kwargs)

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

        The error message is written as a "_node" attribute to the current group
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
