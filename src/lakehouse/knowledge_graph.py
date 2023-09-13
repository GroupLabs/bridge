# purpose: handle knowledge graph storage, and retrieval

from neo4j import GraphDatabase

class Graph:
    
    # CONNECTION
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()
    
    # OPERATIONS
    def add_node(): # create node
        # store name, and metadata (for now just description)
        # meta could just be an attribute of the node
        pass
    
    def del_node(): # delete node
        # delete by name, id, or whatever is easiest
        pass
    
    def add_rel():
        pass
    
    def del_rel():
        pass
    
    def add_triple():
        pass
    
    def del_triple():
        pass
    
    # UTILITY
    def delete_all(self): # delete every node, and relationship
        with self._driver.session() as session:
            session.write_transaction(self._delete_all)
            
    @staticmethod
    def _delete_all(tx):
        query = "MATCH (n) DETACH DELETE n"
        tx.run(query)

        
if __name__ == "__main__":
    # tests - add node, delete node
    
    pass
