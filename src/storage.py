import os
from dotenv import load_dotenv, find_dotenv

from graph import Graph
from search import Search
from metadata import Metadata

load_dotenv(find_dotenv())


class Connector:
    def __init__(self, search: Search, graph: Graph):
        self.search = search
        self.graph = graph

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

        data = [
            "search",
            "graph",
        ]

        return f"available connectors: {str([method for method in dir(self) if method not in (standard_methods + data)])}"

    def pdf(self, input):
        self.search.pdf(input)
        self.graph.pdf(input)

    # def sql(self):
    #     # unstructured -> vespa
    #     # neo4j data importer
    #     pass


class Storage:
    def __init__(self, **kwargs):
        self.graph = Graph(
            kwargs.get("graph_uri", os.getenv("GRAPH_URI")),
            kwargs.get("graph_user", os.getenv("GRAPH_USER")),
            kwargs.get("graph_pass", os.getenv("GRAPH_PASS")),
        )

        self.search = Search()

        self.connector = Connector(self.search, self.graph)

    def __repr__(self):
        r = ""
        r = str(self.graph)
        r = r + "\n"
        r = r + str(self.search)

        return r

    def store(self, input):
        # generate meta
        meta = Metadata.metadata(input)
        name = meta.name
        description = meta.description

        # invoke the apppropriate connector
        if meta.extension == "PDF":
            self.connector.pdf(input)

    def save(self):
        pass

    def query(self, input, k=-1):
        # vespa discover target
        # correlation via graph
        pass


if __name__ == "__main__":
    storage = Storage()

    c = Connector(storage.search, storage.graph)

    print(storage)

    print(c)
