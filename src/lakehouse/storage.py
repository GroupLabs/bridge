# purpose: organize stored data.

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

    def create_nodes_and_relationships(self):
        with self._driver.session() as session:
            session.write_transaction(self._create_nodes_and_relationships)

    @staticmethod
    def _create_nodes_and_relationships(tx):
        # Create nodes
        query = (
            "CREATE (alice:Person {name: 'Alice', age: 30}), "
            "(bob:Person {name: 'Bob', age: 35}), "
            "(eve:Person {name: 'Eve', age: 25}), "
            "(python:Language {name: 'Python'}), "
            "(java:Language {name: 'Java'}) "
            "RETURN alice, bob, eve, python, java"
        )
        tx.run(query)

        # Create relationships
        query = (
            "MATCH (alice:Person {name: 'Alice'}), "
            "(bob:Person {name: 'Bob'}), "
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
    graph = Graph("bolt://localhost:7687", "neo4j", "bridge20")

    graph.delete_all()

    graph.create_nodes_and_relationships()

    graph.close()

    print("Knowledge Graph created!")
