import os
from dotenv import load_dotenv, find_dotenv

from graph import Graph
from search import Search
from metadata import Metadata

load_dotenv(find_dotenv())


class Connector:
    def __init__(self):
        pass

    def __repr__(self) -> str:
        standard_methods = [
            "__class__",
            "__delattr__",
            "__dict__",
            "__dir__",
            "__doc__",
            "__eq__",
            "__format__",
            "__ge__",
            "__getattribute__",
            "__getstate__",
            "__gt__",
            "__hash__",
            "__init__",
            "__init_subclass__",
            "__le__",
            "__lt__",
            "__module__",
            "__ne__",
            "__new__",
            "__reduce__",
            "__reduce_ex__",
            "__repr__",
            "__setattr__",
            "__sizeof__",
            "__str__",
            "__subclasshook__",
            "__weakref__",
        ]
        return str([method for method in dir(self) if method not in standard_methods])

    def pdf():
        # unstructured -> vespa (happens under the hood)
        # neo4j
        pass

    def sql():
        # unstructured -> vespa
        # neo4j data importer
        pass


class Storage:
    def __init__(self, **kwargs):
        self.graph = Graph(
            kwargs.get("graph_uri", os.getenv("GRAPH_URI")),
            kwargs.get("graph_user", os.getenv("GRAPH_USER")),
            kwargs.get("graph_pass", os.getenv("GRAPH_PASS")),
        )

        # self.search = Search()

    def __repr__(self):
        r = ""
        r = r + "Graph: \n"
        # r = r + f".... storing {len(self.graph)} value(s)" # graph info
        r = r + "Search: \n"
        # r = r + f".... storing {len(self.search)} value(s)"

        return r

    def store(self, input):
        # generate meta
        meta = Metadata.metadata(input)
        name = meta.name
        description = meta.description

        # invoke the apppropriate connector
        # if meta.extension

    def save(self):
        pass

    def query(self, input, k=-1):
        # vespa discover target
        # correlation via graph
        pass


if __name__ == "__main__":
    storage = Storage()

    c = Connector()

    print(storage)

    print(c)