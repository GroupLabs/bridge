# purpose: handle knowledge graph storage, and retrieval

from neo4j import GraphDatabase

class Graph:
    
    # CONNECTION
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    # OPERATIONS
    def add_node(self, name, description):
        with self._driver.session() as session:
            session.execute_write(self._create_node, name, description)
    
    @staticmethod
    def _create_node(tx, name, description):
        query = "CREATE (a:Node {name: $name, description: $description}) RETURN a"
        tx.run(query, name=name, description=description)

    def del_node(self, name):
        with self._driver.session() as session:
            session.execute_write(self._delete_node, name)
    
    @staticmethod
    def _delete_node(tx, name):
        query = "MATCH (a:Node {name: $name}) DELETE a"
        tx.run(query, name=name)

    def add_rel(self, name1, name2, relation):
        with self._driver.session() as session:
            session.execute_write(self._create_rel, name1, name2, relation)
    
    @staticmethod
    def _create_rel(tx, name1, name2, relation):
        query = "MATCH (a:Node {name: $name1}), (b:Node {name: $name2}) CREATE (a)-[:%s]->(b)" % relation
        tx.run(query, name1=name1, name2=name2)

    def del_rel(self, name1, name2, relation):
        with self._driver.session() as session:
            session.execute_write(self._delete_rel, name1, name2, relation)

    @staticmethod
    def _delete_rel(tx, name1, name2, relation):
        query = "MATCH (a:Node {name: $name1})-[r:%s]->(b:Node {name: $name2}) DELETE r" % relation
        tx.run(query, name1=name1, name2=name2)
    
    def add_triple(self, name1, name2, relation, description1, description2):
        with self._driver.session() as session:
            session.execute_write(self._add_triple, name1, name2, relation, description1, description2)

    @staticmethod
    def _add_triple(tx, name1, name2, relation, description1, description2):
        query = """
        CREATE (a:Node {name: $name1, description: $description1}),
               (b:Node {name: $name2, description: $description2})
        CREATE (a)-[:%s]->(b)
        """ % relation
        tx.run(query, name1=name1, name2=name2, description1=description1, description2=description2)
        
    def del_triple(self, name1, name2, relation):
        with self._driver.session() as session:
            session.execute_write(self._del_triple, name1, name2, relation)

    @staticmethod
    def _del_triple(tx, name1, name2, relation):
        query = """
        MATCH (a:Node {name: $name1})-[r:%s]->(b:Node {name: $name2})
        DELETE a, b, r
        """ % relation
        tx.run(query, name1=name1, name2=name2)

    # UTILITY
    def delete_all(self):
        with self._driver.session() as session:
            session.execute_write(self._delete_all)

    @staticmethod
    def _delete_all(tx):
        query = "MATCH (n) DETACH DELETE n"
        tx.run(query)
        
if __name__ == "__main__":
    g = Graph("bolt://localhost:7687", "neo4j", "eternal-pyramid-corner-jester-bread-6973") # replace with your user, pass

    # Add a single node
    g.add_node("Alice", "Developer")

    # Delete a single node
    g.del_node("Alice")

    # # Add a relationship between two existing nodes "Alice" and "Bob"
    g.add_rel("Alice", "Bob", "KNOWS")

    # # Delete the relationship between "Alice" and "Bob"
    g.del_rel("Alice", "Bob", "KNOWS")

    # # Add a triple
    g.add_triple("Alice", "Bob", "KNOWS", "Developer", "Designer")

    # # Delete a triple
    g.del_triple("Alice", "Bob", "KNOWS")

    # # Delete all nodes and relationships
    g.delete_all()

    # Close the connection
    g.close()

    
    pass
