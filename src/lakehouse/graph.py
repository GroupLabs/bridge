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

    # Basic read query
    def query(self, query: str):
        records, summary, keys = self._driver.execute_query(
            query
        )
        return records # don't care about other things
    
    def node_traversal(self, name_node_one, name_node_two, max_traversal: int = 3):
        query = f"""
                MATCH path = (START:TABLE {{name : "{name_node_one}"}})-[*..{max_traversal}]->(end:TABLE {{name: "{name_node_two}"}}) RETURN path;
                """
        result = self.query(query)
        processed_dict = self._process_node_traversal_result(result)
        return processed_dict
    
    def _process_node_traversal_result(self, result):
        path_ways = {}
        for index, record in enumerate(result):
            relationships = []
            for relationship in record[0]:
                join = relationship.get("key")
                relationships.append(join)
                # print(join)
            path_ways[f"path{index}"] = relationships
        return path_ways
    
            
    # Add Tree Traversal
    # NODE TRAVERSAL
    # MATCH path = (start:TABLE {name: 'Students'})-[*..3]->(end:TABLE {name: 'Classes'}) RETURN path;
    # https://stackoverflow.com/questions/63563077/neo4j-how-to-return-all-paths-from-a-selected-starting-node
    # def node_traversal(self, name_node_one, name_node_two, max_traversal = 3):
    #     def _node_traversal(tx, name_node_one, name_node_two, max_traversal):
    #         query = f"""
    #             MATCH path = (START:TABLE {{name : "{name_node_one}"}})-[*..{max_traversal}]->(end:TABLE {{name: "{name_node_two}"}}) RETURN path;
    #             """
    #         result = tx.run(query)
    #         return result
    #     with self._driver.session() as session:
    #         return session.execute_read(_node_traversal, name_node_one, name_node_two, max_traversal)  
        
    #     # with self._driver.session() as session:
    #     #     traversal = session.execute_read(lambda tx: tx.run(f"""
    #     #         MATCH path = (START:TABLE {{name : "{name_node_one}"}})-[*..{max_traversal}]->(end:TABLE {{name: "{name_node_two}"}}) RETURN path;
    #     #         """))
            
    #     #     return traversal

    # OPERATIONS
    def add_table_node(self, name, primary_key, columns, labels):
        def _create_table(tx, name, primary_key, columns, labels):
            query = f"""
            CREATE ({name}:{labels} {{name: "{name}", primaryKey: "{primary_key}", columns: {columns}}});
            """
            return tx.run(
                query
            ).single()
            
        with self._driver.session() as session:
            session.execute_write(_create_table, name, primary_key, columns, labels)
            
    def add_basic_node(self, name, description, labels):
        def _create_node(tx, name, description, labels):
            query = f"""
            CREATE ({name}:{labels} {{name: "{name}", description: "{description}"}});
            """
            return tx.run(
                query
            ).single()
            
        with self._driver.session() as session:
            session.execute_write(_create_node, name, description, labels)
    
    # Utility Functions
    def delete_all(self):
        def _delete_all(tx):
            query = "MATCH (n) DETACH DELETE n"
            return tx.run(
                query
            )
            
        with self._driver.session() as session:
            session.execute_write(_delete_all)
            
    def delete_node(self, name):
        # need to delete relationships first, which is DETACH keyword
        # Node names SHOULD be unique - will add functionality to add query to check for unique names or else it will just delete all nodes with name
        def _delete_node_name(tx, name):
            query = f"""
            MATCH (n {{name: "{name}"}}) DETACH DELETE n
            """
            return tx.run(
                query
            )
        
        with self._driver.session() as session:
            session.execute_write(_delete_node_name, name)
            
    def add_pandas_table_node(self, pandas_dataframe, name, primary_key, labels):
        
        def _create_node(tx, pandas_dataframe, name, primary_key, labels):
            query = f"""
            CREATE ({name}:{labels} {{name: "{name}", primaryKey: "{primary_key}", columns: {pandas_dataframe.columns.tolist()}}});
            """
            return tx.run(
                query
            )
            
        with self._driver.session() as session:
            session.execute_write(_create_node, pandas_dataframe, name, primary_key, labels)
            
    def add_relationship(self, name_node_one, name_node_two, relation_name):
        
        def _add_relation(tx, name_node_one, name_node_two, relation_name):
            query = f"""
            MATCH (a {{name : "{name_node_one}"}}), (b {{name: "{name_node_two}"}})
            CREATE (a) -[:{relation_name}]-> (b)
            """
            return tx.run(
                query
            )
        with self._driver.session() as session:
            session.execute_write(_add_relation, name_node_one, name_node_two, relation_name)
    
    # Meant to add relationships of every direction to the knowledge graph. Built with list structure of a list of lists        
    def add_list_key_relationships(self, table_relationships: list, relation_name: str):
        for relationship in table_relationships:
            node_one = relationship[0]
            node_two = relationship[1] 
            key = f"""{relation_name} {{key : "{relationship[2]}"}}"""
            # print(node_one, node_two, key)
            self.add_relationship(name_node_one= node_one, name_node_two= node_two, relation_name= key)
            
    def delete_relationship(self, name_node_one, name_node_two, relation_name):
        
        def _delete_relation(tx, name_node_one, name_node_two, relation_name):
            query = f"""
            MATCH(a {{name : "{name_node_one}"}})-[r:{relation_name}]->(b {{name: "{name_node_two}"}})
            DELETE r
            """
            return tx.run(
                query
            )
        with self._driver.session() as session:
            session.execute_write(_delete_relation, name_node_one, name_node_two, relation_name)
            
    ## Bidirectional join function instead of single direction
    def add_bidirectional_relationship(self, name_node_one, name_node_two, name_relationship):
        self.add_relationship(name_node_one, name_node_two, name_relationship)
        self.add_relationship(name_node_two, name_node_one, name_relationship)
    
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
        
    def get_node_count(self):
        with self._driver.session() as session:
            session.execute_write(self._get_node_count)
    
    @staticmethod
    def _get_node_count(tx):
        # This Cypher query will count the number of nodes in the graph.
        result = tx.run("MATCH (n) RETURN count(n) AS node_count")
        return result.single()["node_count"]
        
if __name__ == "__main__":
    load_dotenv()
    
    g = Graph(os.getenv("GRAPH_URI"), os.getenv("GRAPH_USER"), os.getenv("GRAPH_PASS")) # replace with your user, pass
    
    g = Graph("bolt://localhost:7687", "neo4j", "eternal-pyramid-corner-jester-bread-6973")
    
    # g.delete_all()
    # g = Graph("bolt://localhost:7687", "neo4j", "eternal-pyramid-corner-jester-bread-6973") 

    # # Add a single node
    # g.add_basic_node("Alice", labels="Developer", description=["temp", "eugenes lover"])
    # g.add_basic_node("Bob", labels="Developer", description=["temp", "eugenes lover2"])
    
    # # Delete a single node
    # g.delete_node("Alice")

    # # # Add a relationship between two existing nodes "Alice" and "Bob"
    # g.add_relationship("Alice", "Bob", "KNOWS")

    # # # Delete the relationship between "Alice" and "Bob"
    # g.delete_relationship("Alice", "Bob", "KNOWS")

    # # Add a triple
    # g.add_triple("Alice", "Bob", "KNOWS", "Developer", "Designer")

    # # Delete a triple
    # g.del_triple("Alice", "Bob", "KNOWS")

    # # Delete all nodes and relationships
    # g.delete_all()
    
    
    print(g.get_node_count())

    # Close the connection
    g.close()

    
    pass
