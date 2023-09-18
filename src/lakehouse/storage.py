# purpose: convert and tag inbound data.

import csv
import os

from knowledge_graph import Graph

kg = Graph("bolt://localhost:7687", "neo4j", "eternal-pyramid-corner-jester-bread-6973")

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
        self._extension = None
        self._is_structured = None
        
    def __repr__(self) -> str:
        r = ''
        r = r + f"ext: {self._extension}\n"
        r = r + f"structured: {self._is_structured}"
        
        return r

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


def metadata(input):
    
    metadata = Metadata()
    
    if isinstance(input, str):
        if os.path.exists(input):
            _, ext = os.path.splitext(input)
            
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
                return f"WARN: Unsupported {ext} extension."
        else:
            return "The input is a string but not a file path."
    return metadata

def store(input):
    
    # generate file meta (struct/unstruct)
    # store node (name, desc; meta: ...)
    # store vec (desc; meta: document name)
    
    pass
    
    

if __name__ == "__main__":
    m = metadata("hello.txt")
    print(m)
