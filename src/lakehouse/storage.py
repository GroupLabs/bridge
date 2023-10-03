# purpose: convert and tag inbound data.
import csv
import os
from dotenv import load_dotenv, find_dotenv
import pandas as pd
from enum import Enum
from .graph import Graph
from .vector_store import VectorStore
from .metadata import Metadata

load_dotenv(find_dotenv())

class Storage:
    def __init__(self, **kwargs):
        self.graph = Graph(
            kwargs.get("graph_uri", os.getenv("GRAPH_URI")), 
            kwargs.get("graph_user", os.getenv("GRAPH_USER")), 
            kwargs.get("graph_pass", os.getenv("GRAPH_PASS"))
            )
        self.vec_store = VectorStore(kwargs.get("vec_store_loadfile", None))
        
    def __repr__(self):
        r = ""
        r = r + "Graph: \n"
        # graph info add here
        r = r + "Vector Storage: \n"
        r = r + f".... storing {len(self.vec_store.values)} value(s)"
        
        return r
        
    def store(self, input):
        # generate file meta (struct/unstruct)
        if input.endswith(".desc"):
            return
        meta = Metadata.metadata(input)
        name = meta.name
        description = meta.description
        # store node (name, desc; meta: ...)
        # self.graph.storenode
        # A function that stores
        if meta.is_structured:
            primary_keys = meta.contents.get(name).get("keys")
            columns = meta.contents.get(name).get("columns")
            self.graph.add_table_node(name, primary_keys, columns, labels="TABLE")
        else:
            self.graph.add_basic_node(name, description, labels="UNSTRUCTURED")
        
        # store vec (desc; meta: document name)
        self.vec_store.store_object(meta.as_object())
        
    def save(self, name):
        # save/close conn of graph
        self.graph.close()
        
        # save index and values
        self.vec_store.save(name)
        
    # Store a list of inputs
    def store_list(self, list: list):
        for input in list:
            self.store(input)
    
    def create_relationship(self, name1, name2, relation):
        self.graph.add_bidirectional_relationship(name1, name2, relation)
    
    def _create_dictionary_structured(self, input_list: list):
        df_dict = {}
        for input in input_list:
            if ".desc" in input:
                print(f"Skipping {input} as it's a description file")
                continue
            meta = Metadata.metadata(input)
            if not meta.is_structured:
                print("This function is for structured data!")
                return
            name = meta.name
            df_dict[name] = meta.contents.get(name)
        return df_dict
    
    def _auto_detect_relationships(self, df_dict : dict):
        table_relationships = []
        for table1, dict1 in df_dict.items():
            keys1 = dict1.get("keys")
            for table2, dict2 in df_dict.items():
                keys2 = dict2.get("keys")
                if table1 != table2:
                    shared_keys = list(set(keys1) & set(keys2))
                    if shared_keys:
                        for i, shared_key in enumerate(shared_keys, start = 1):
                            table_relationships.append((table1, table2, f"{table1}.{shared_key} = {table2}.{shared_key}", i))
        return table_relationships
    
    def create_relationships_structured(self, input_list: list):
        df_dict = self._create_dictionary_structured(input_list)
        
        table_relationships = self._auto_detect_relationships(df_dict)
        
        for relationship in table_relationships:
            node_one = relationship[0]
            node_two = relationship[1] 
            key = f"""JOIN {{key : "{relationship[2]}"}}"""
            # print(node_one, node_two, key)
            self.graph.add_relationship(name_node_one= node_one, name_node_two= node_two, relation_name= key)
        
    def query(self, input, k=-1):
        
        # query vector store
        relevant_tables = self.vec_store.query(input, k)
        
        table_names = []
        for _index, dictionary in enumerate(relevant_tables):
            # Use dict.get() to safely get the value of the 'name' key if it exists,
            # or None if it doesn't exist
            name_value = dictionary.get('name')
            
            if name_value is not None:
                table_names.append(name_value)
        
        # traversal
        nodes = self.graph.node_traversal(table_names[0], table_names[1], 2)
        
        return nodes

if __name__ == "__main__":
    storage = Storage()
    
    storage.store("../../data/hello.txt")
    
    print(storage)
    
    storage.save('test')  # always overwrites test
