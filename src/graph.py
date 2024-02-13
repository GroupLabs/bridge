from neo4j import GraphDatabase
import os

from unstructured.partition.pdf import partition_pdf


class Graph:
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def __len__(self):
        query = "MATCH (n) RETURN COUNT(n) AS node_count"

        with self._driver.session() as session:
            result = session.run(query)
            return result.single()[0]

    def __repr__(self):
        r = ""
        r = r + "Graph: \n"
        try:
            with self._driver.session() as session:
                session.run("RETURN 'Connection Successful'")
            r = r + f".... status: healthy\n"
            r = r + f".... storing {len(self)} value(s)"
        except Exception as e:
            r = r + f".... status: fail"  # graph info

        return r

    def __del__(self):
        self._driver.close()

    def cypher_query(self, query: str):
        return self._driver.execute_query(query)

    # connectors

    def pdf(self, name):
        elements = partition_pdf(name, strategy="fast")

        def _create_node(tx, _name):
            query = "CREATE (n:PDF {name: $name})"
            return tx.run(query, name=_name).single()

        with self._driver.session() as session:
            session.execute_write(
                _create_node, elements[0].metadata.to_dict()["filename"]
            )

    # algorithms

    def correlation():
        # https://neo4j.com/docs/graph-data-science/current/algorithms/pregel-api/
        pass

    # utils

    def delete_all(self):
        def _delete_all(tx):
            query = "MATCH (n) DETACH DELETE n"
            return tx.run(query)

        with self._driver.session() as session:
            session.execute_write(_delete_all)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    g = Graph(os.getenv("GRAPH_URI"), os.getenv("GRAPH_USER"), os.getenv("GRAPH_PASS"))

    g.delete_all()

    g.pdf(
        "/Users/noelthomas/Documents/GitHub/Bridge/data/datasets/pdf_tressl/Summary Report.pdf"
    )

    print(len(g))

    print(g)
