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

    def sql():
        # https://www.google.com/url?sa=t&rct=j&q=&esrc=s&source=web&cd=&cad=rja&uact=8&ved=2ahUKEwio5cLh3qeEAxXSLzQIHQm7BCs4ChAWegQICRAB&url=https%3A%2F%2Fdl.acm.org%2Fdoi%2F10.1145%2F2484425.2484426&usg=AOvVaw1SSCXxig-TYumhrc3fJ_GK&opi=89978449
        # https://medium.com/neo4j/tap-into-hidden-connections-translating-your-relational-data-to-graph-d3a2591d4026
        pass

    # algorithms

    def correlation():
        # https://neo4j.com/docs/graph-data-science/current/algorithms/pregel-api/

        # prevent cyclic graphs!
        # https://neo4j.com/docs/graph-data-science/current/algorithms/dag/topological-sort/#topological-sort-cycles
        pass

    # utils

    def delete_all(self):
        def _delete_all(tx):
            query = "MATCH (n) DETACH DELETE n"
            return tx.run(query)

        with self._driver.session() as session:
            session.execute_write(_delete_all)


if __name__ == "__main__":
    pass
