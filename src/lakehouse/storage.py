# purpose: convert and tag inbound data.

def store(input): # store input in lakehouse
    
    # is the input an (a) unstructured, or (b) structured file path?
    
    # (a) structured
        # store each column as node (id, name, desc) in knowledge graph
        # store metadata vectors (id, name, desc) in vector store
    
    # (b) unstructured
        # store file metadata as node (id, name, desc) in knowledge graph
        # store metadata vectors (id, name, desc) in vector store
    pass

import csv
import os

def is_structured(file_path):
    # Check the file extension; for demonstration
    return file_path.endswith('.csv')

def vectorize_metadata(id, name, desc):
    # Simple example; this function should actually convert text to vectors
    return f"Vector({id},{name},{desc})"

def store_in_knowledge_graph(id, name, desc):
    print(f"Storing in Knowledge Graph: ID: {id}, Name: {name}, Desc: {desc}")

def store_in_vector_store(vector):
    print(f"Storing in Vector Store: {vector}")

def store(input):
    if is_structured(input):
        # Reading CSV and storing each column as a node in the knowledge graph
        with open(input, 'r') as f:
            reader = csv.reader(f)
            headers = next(reader, None)  # Get the headers of CSV
            
            for header in headers:
                id = header  # ID is the column name for this example
                name = f"Column {header}"
                desc = f"This column contains {header} data"
                
                # Storing in knowledge graph
                store_in_knowledge_graph(id, name, desc)
                
                # Vectorizing and storing in vector store
                metadata_vector = vectorize_metadata(id, name, desc)
                store_in_vector_store(metadata_vector)
                
    else:
        # For unstructured data, we are storing file metadata
        id = os.path.basename(input)
        name = "Unstructured File - {id}"
        desc = f"This is an unstructured file with name {id}"
        
        # Storing in knowledge graph
        store_in_knowledge_graph(id, name, desc)
        
        # Vectorizing and storing in vector store
        metadata_vector = vectorize_metadata(id, name, desc)
        store_in_vector_store(metadata_vector)
        
# Testing the function
store("structured.csv")
store("unstructured.txt")


if __name__ == "__main__":
    pass
