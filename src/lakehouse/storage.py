# purpose: convert and tag inbound data.

import csv
import os
from dotenv import load_dotenv

from knowledge_graph import Graph
from vector_store import VectorStore

load_dotenv()

from enum import Enum

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
        
    def __repr__(self) -> str:
        r = ''
        r = r + f"name: {self._name}\n"
        r = r + f"ext: {self._extension}\n"
        r = r + f"structured: {self._is_structured}\n"
        r = r + f"description: {self._description}"
        
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
    
    def as_object(self):
        obj = {}
        obj["name"] = self._name
        obj["extension"] = self._extension
        obj["structured"] = self._is_structured
        obj["description"] = self._description
        
        return obj


def metadata(input):
    
    metadata = Metadata()
    
    if isinstance(input, str):
        if os.path.exists(input):
            name, ext = os.path.splitext(input)
            
            metadata.name = name
            
            # get description from desc file
            with open(f'{name}.desc', 'r') as f:
                metadata.description = f.read()
            
            # structured
            if ext.lower() == '.csv':
                metadata.extension = "CSV"
                metadata.is_structured = True
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

            else:
                raise NotImplementedError(f"WARN: Unsupported {ext} extension.")
        else:
            raise ValueError("Input to metadata function is a string but not a file path.")
    return metadata

class Storage:
    def __init__(self, **kwargs):
        self.kg = Graph(
            kwargs.get("graph_uri", os.getenv("GRAPH_URI")), 
            kwargs.get("graph_user", os.getenv("GRAPH_USER")), 
            kwargs.get("graph_pass", os.getenv("GRAPH_PASS"))
            )
        self.vs = VectorStore(kwargs.get("vs_loadfile", None))
        
    def __repr__(self):
        r = ""
        r = r + "Graph: \n"
        r = r + "Vector Storage: \n"
        r = r + f".... storing {len(self.vs.values)} value(s)"
        
        return r
        
        
    def store(self, input):
        # generate file meta (struct/unstruct)
        meta = metadata(input)
        
        # store node (name, desc; meta: ...)
        
        # store vec (desc; meta: document name)
        self.vs.store_object(meta.as_object())
        
    def save(self, name):
        # save/close conn of graph
        
        # save index and values
        self.vs.save(name)


if __name__ == "__main__":
    storage = Storage()
    
    storage.store("../../data/hello.txt")
    
    print(storage)
    
    storage.save('test')  # always overwrites test
