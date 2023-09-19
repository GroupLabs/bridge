# purpose: handle knowledge graph storage, and retrieval

from neo4j import GraphDatabase
import pandas as pd
from dotenv import load_dotenv, find_dotenv
import os

class Graph:
    
    # CONNECTION
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    # OPERATIONS
    def add_table_node(self, name, primary_key, columns, labels):
        
        def create_table(tx, name, primary_key, columns, labels):
            query = f"""
            CREATE ({name}:{labels} {{name: "{name}", primaryKey: "{primary_key}", columns: {columns}}});
            """
            return tx.run(
                query
            ).single()
            
        with self._driver.session() as session:
            session.execute_write(create_table, name, primary_key, columns, labels)
            
    def add_basic_node(self, name, description, labels):
        
        def create_node(tx, name, description, labels):
            query = f"""
            CREATE ({name}:{labels} {{name: "{name}", description: "{description}"}});
            """
            return tx.run(
                query
            ).single()
            
        with self._driver.session() as session:
            session.execute_write(create_node, name, description, labels)
    
    # Utility Functions
    def delete_all(self):
        
        def delete_all(tx):
            query = "MATCH (n) DETACH DELETE n"
            return tx.run(
                query
            )
            
        with self._driver.session() as session:
            session.execute_write(delete_all)
            
    def delete_node(self, name):
        # need to delete relationships first, which is DETACH keyword
        # Node names SHOULD be unique - will add functionality to add query to check for unique names or else it will just delete all nodes with name
        def delete_node_name(tx, name):
            query = f"""
            MATCH (n {{name: "{name}"}}) DETACH DELETE n
            """
            return tx.run(
                query
            )
        
        with self._driver.session() as session:
            session.execute_write(delete_node_name, name)
            
    def add_pandas_table_node(self, pandas_dataframe, name, primary_key, labels):
        
        def create_node(tx, pandas_dataframe, name, primary_key, labels):
            query = f"""
            CREATE ({name}:{labels} {{name: "{name}", primaryKey: "{primary_key}", columns: {pandas_dataframe.columns.tolist()}}});
            """
            return tx.run(
                query
            )
            
        with self._driver.session() as session:
            session.execute_write(create_node, pandas_dataframe, name, primary_key, labels)
            
    def add_relationship(self, name_node_one, name_node_two, relation_name):
        
        def add_relation(tx, name_node_one, name_node_two, relation_name):
            query = f"""
            MATCH (a {{name : "{name_node_one}"}}), (b {{name: "{name_node_two}"}})
            CREATE (a) -[:{relation_name}]-> (b)
            """
            return tx.run(
                query
            )
        with self._driver.session() as session:
            session.execute_write(add_relation, name_node_one, name_node_two, relation_name)
            
    def delete_relationship(self, name_node_one, name_node_two, relation_name):
        
        def delete_relation(tx, name_node_one, name_node_two, relation_name):
            query = f"""
            MATCH(a {{name : "{name_node_one}"}})-[r:{relation_name}]->(b {{name: "{name_node_two}"}})
            DELETE r
            """
            return tx.run(
                query
            )
        with self._driver.session() as session:
            session.execute_write(delete_relation, name_node_one, name_node_two, relation_name)
    
    def add_join_table_relationship(self, name_node_one, name_node_two, name_join_table):
        self.add_relationship(name_node_one, name_node_two, "JOIN_TABLE_NEEDED")
        self.add_relationship(name_node_two, name_node_one, "JOIN_TABLE_NEEDED")
        self.add_relationship(name_node_one, name_join_table, "JOIN")
        self.add_relationship(name_node_two, name_join_table, "JOIN")
                    
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
        
if __name__ == "__main__":
    g = Graph("bolt://localhost:7687", "neo4j", "eternal-pyramid-corner-jester-bread-6973")

    # Add a single node
    g.add_basic_node("Alice", "Developer", labels=["temp", "eugenes lover"])
    g.add_basic_node("Bob", "Developer", labels=["temp", "eugenes lover2"])
    
    # Delete a single node
    g.delete_node("Alice")

    # # Add a relationship between two existing nodes "Alice" and "Bob"
    g.add_relationship("Alice", "Bob", "KNOWS")

    # # Delete the relationship between "Alice" and "Bob"
    g.delete_relationship("Alice", "Bob", "KNOWS")

    # # Add a triple
    g.add_triple("Alice", "Bob", "KNOWS", "Developer", "Designer")

    # # Delete a triple
    g.del_triple("Alice", "Bob", "KNOWS")

    # # Delete all nodes and relationships
    g.delete_all()

    # Close the connection
    g.close()

    
    pass
