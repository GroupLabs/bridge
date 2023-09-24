# purpose: convert and tag inbound data.

import csv
import os
from dotenv import load_dotenv, find_dotenv
import pandas as pd
from enum import Enum
from graph import Graph
from vector_store import VectorStore

load_dotenv(find_dotenv())


class AllowedExtensions(Enum):
    
    # structured
    CSV = 'CSV'
    TSV = 'TSV'
    PARQUET = 'PARQUET'
    
    # unstructured
    TXT = 'TXT'
    PDF = 'PDF'

class Metadata:
    def __init__(self):
        self._name = None
        self._extension = None
        self._is_structured = None
        self._description = None
        self._contents = None
        
    def __repr__(self) -> str:
        r = ''
        r = r + f"name: {self._name}\n"
        r = r + f"ext: {self._extension}\n"
        r = r + f"structured: {self._is_structured}\n"
        r = r + f"description: {self._description}\n"
        r = r + f"contents: {self._contents}"
        
        return r
    
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value

    @property
    def extension(self):
        return self._extension

    @extension.setter
    def extension(self, value: str):
        if value not in AllowedExtensions.__members__:
            raise ValueError("Extension must be one of: " + ", ".join(AllowedExtensions.__members__))
        
        self._extension = AllowedExtensions[value].value
        
    @property
    def is_structured(self):
        return self._is_structured

    @is_structured.setter
    def is_structured(self, value: bool):
        self._is_structured = value
        
        
    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, value: str):
        self._description = value    
        
    @property
    def contents(self):
        return self._contents

    @contents.setter
    def contents(self, value):
        self._contents = value    
        
        
    
    def as_object(self):
        obj = {}
        obj["name"] = self._name
        obj["extension"] = self._extension
        obj["structured"] = self._is_structured
        obj["description"] = self._description
        obj["contents"] = self._contents
        
        return obj
    
    def csv_extraction(self, name, input):
        df_dict = {}
        df = pd.read_csv(input, encoding = 'latin-1')
        df_keys = []
        for column in df.columns.tolist():
            if ("id") in column.lower():
                df_keys.append(column)
        df_dict[name] = {"columns" : df.columns.tolist(),
                "keys": df_keys}
        return df_dict


def metadata(input):
    
    metadata = Metadata()
    
    if isinstance(input, str):
        if os.path.exists(input):
            file_name = os.path.basename(input) # Gets rid of file path if a file path is used
            name, ext = os.path.splitext(file_name)
            
            metadata.name = name
            
            # get description from desc file
            # This doesn't seem to work for now, takes all file and assumes they are .desc
            if os.path.exists(f'{name}.desc'):
                with open(f'{name}.desc', 'r') as f:
                    metadata.description = f.read()
            else: 
                print(f"No description file provided for {name}{ext}")
                metadata.description = "No description file provided"
            
            # structured
            if ext.lower() == '.csv':
                metadata.extension = "CSV"
                metadata.is_structured = True
                df_dict = metadata.csv_extraction(name, input)
                metadata.contents = df_dict
                ## Add columns variable to metadata for csvs
            elif ext.lower() == '.tsv':
                metadata.extension = "TSV"
                metadata.is_structured = True
            elif ext.lower() == '.parquet':
                metadata.extension = "PARQUET"
                metadata.is_structured = True
            
            # unstructured
            elif ext.lower() == '.txt':
                metadata.extension = "TXT"
                metadata.is_structured = False
            elif ext.lower() == '.pdf':
                metadata.extension = "PDF"
                metadata.is_structured = False

            # if unstructured:
            # store a new vs, content is vecstore fp
            # else
            # store columns in content

            else:
                raise NotImplementedError(f"WARN: Unsupported {ext} extension.")
        else:
            raise ValueError("Input to metadata function is a string but not a file path.")
    return metadata

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
        meta = metadata(input)
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
        # self.vs.store_object(meta.as_object())
        
    def save(self, name):
        # save/close conn of graph
        self.graph.close()
        
        # save index and values
        # self.vs.save(name)
        
    # Store a list of inputs
    def store_list(self, list: list):
        for input in list:
            self.store(input)
    
    def create_relationship(self, name1, name2, relation):
        self.graph.add_bidirectional_relationship(name1, name2, relation)
    
    def _create_dictionary_structured(self, input_list: list):
        df_dict = {}
        for input in input_list:
            meta = metadata(input)
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

if __name__ == "__main__":
    storage = Storage()
    
    storage.store("../../data/hello.txt")
    
    print(storage)
    
    storage.save('test')  # always overwrites test
