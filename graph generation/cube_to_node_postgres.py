import neo4j
import pandas as pd
import numpy as np
import yaml 

from neo4j import GraphDatabase
import os 
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(r"C:\Users\Eugene\Documents\GroupLabs\bridge\MySQL_Cubes_Nodes\.env"))

### THIS HAS TO BE RUN 2 TIMES TO CAPTURE ALL FK,PK RELATIONSHIPS

class GraphCreator:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def process_yaml(self, yaml_path):
        with open(yaml_path, 'r') as file:
            yaml_data = yaml.safe_load(file)
            self.create_graph_from_yaml(yaml_data)
    
    def test_connection(self):
        with self.driver.session() as session:
            result = session.run("RETURN 1")
            return result.single()[0] == 1

    def table_exists(self, table_name):
        with self.driver.session() as session:
            result = session.run("MATCH (t:Table {name: $name}) RETURN t", name=table_name)
            return result.single() is not None

    def create_graph_from_yaml(self, yaml_data):
        with self.driver.session() as session:
            # Check if the table node already exists
            if not self.table_exists(yaml_data['name']):
                session.write_transaction(self._create_table_node_with_dimensions, yaml_data)
                if 'joins' in yaml_data:
                    for join in yaml_data['joins']:
                        session.write_transaction(self._create_join_relationship, yaml_data['name'], join)
            else:
                print(f"Table node for '{yaml_data['name']}' already exists. Skipping creation. Double-checking relationships...")
                
                if 'joins' in yaml_data:
                    for join in yaml_data['joins']:
                        session.write_transaction(self._create_join_relationship, yaml_data['name'], join)

    @staticmethod
    def _create_table_node_with_dimensions(tx, table_info):
        # Serialize dimensions for storage in the node
        dimensions = yaml.dump(table_info.get('dimensions', []))
        # Initialize joins to a default value
        joins = yaml.dump(table_info.get('joins', []))  # Serialize empty list if no joins
        
        # Determine if we need to include joins in the properties
        if joins != '[]':  # Assuming serialized empty list is '[]'
            tx.run("""
                MERGE (t:Table {name: $name, sql_name: $sql_name, dimensions: $dimensions, joins: $joins})
                """,
                name=table_info['name'],
                sql_name=table_info.get('sql_name', ''),
                dimensions=dimensions,
                joins=joins)
        else:
            tx.run("""
                MERGE (t:Table {name: $name, sql_name: $sql_name, dimensions: $dimensions})
                """,
                name=table_info['name'],
                sql_name=table_info.get('sql_name', ''),
                dimensions=dimensions)
    
    @staticmethod
    def _create_join_relationship(tx, table_name, join_info):
        # Create a relationship based on the join information
        tx.run("""
            MATCH (t1:Table {name: $table_name}), (t2:Table {name: $join_name})
            MERGE (t1)-[:JOINS {sql: $join_sql}]->(t2)
            """, table_name=table_name, join_name=join_info['name'], join_sql=join_info['sql'])
        
        # Extend this method to handle relationships based on your YAML structure

# Example Usage
uri = os.getenv("GRAPH_URI")
username = os.getenv("GRAPH_USER")
password = os.getenv("GRAPH_PWD")
graph_creator = GraphCreator(uri, username, password)
graph_creator.test_connection()
yamls_path = r'C:\Users\Eugene\Documents\GroupLabs\bridge\MySQL_Cubes_Nodes\PostgreSql\models\cubes\\'  # Update this path to your YAML file

for cube in os.listdir(yamls_path):

    graph_creator.process_yaml(yamls_path + cube)

#graph_creator.process_yaml(yaml_path)
graph_creator.close()

### TO DO - ERROR HANDLING