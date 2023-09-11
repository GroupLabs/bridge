# purpose: organize stored data.

# unstructured: store as new faiss index
# structured: each column is its own entity

from neo4j import GraphDatabase

class Graph:
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def delete_all(self):
        with self._driver.session() as session:
            session.write_transaction(self._delete_all)
            
    @staticmethod
    def _delete_all(tx):
        query = "MATCH (n) DETACH DELETE n"
        tx.run(query)

    def query(self, *query):
        with self._driver.session() as session:
            session.write_transaction(self._query, *query)

    @staticmethod
    def _query(tx, *query):
        # Create nodes
        query = (query)
        tx.run(query)

        # Create relationships
        query = (
            "MATCH (alice:Person {name: 'Alice'}), " "(bob:Person {name: 'Bob'}), "
            "(eve:Person {name: 'Eve'}), "
            "(python:Language {name: 'Python'}), "
            "(java:Language {name: 'Java'}) "
            "CREATE (alice)-[:KNOWS]->(bob), "
            "(alice)-[:KNOWS]->(eve), "
            "(alice)-[:LIKES]->(python), "
            "(bob)-[:LIKES]->(java)"
        )
        tx.run(query)

if __name__ == "__main__":
    graph = Graph("bolt://localhost:7687", "neo4j", "eternal-pyramid-corner-jester-bread-6973")

    graph.delete_all()

    graph.query("h")

    graph.close()

    print("Knowledge Graph created!")
