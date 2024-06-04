import pymongo
from pymongo import MongoClient
import ssl
import yaml
import pprint

def get_mongo_connection(uri):
    try:
        client = MongoClient(uri, tls=True, tlsAllowInvalidCertificates=True)
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
        return client
    except Exception as e:
        print(f"An error occurred while connecting to MongoDB: {e}")
        return None

def get_all_databases(client):
    try:
        databases = client.list_database_names()
        print(f"Detected databases: {databases}")
        return databases
    except Exception as e:
        print(f"An error occurred while fetching databases: {e}")
        return []

def get_all_collections(db):
    try:
        collections = db.list_collection_names()
        print(f"Detected collections in database '{db.name}': {collections}")
        return collections
    except Exception as e:
        print(f"An error occurred while fetching collections: {e}")
        return []

def get_collection_schema(collection):
    schema = {}
    try:
        sample_doc = collection.find_one()
        if sample_doc:
            for field, value in sample_doc.items():
                schema[field] = type(value).__name__
        print(f"Schema for collection '{collection.name}': {schema}")
    except Exception as e:
        print(f"An error occurred while fetching collection schema: {e}")
    return schema

def mongo_to_yamls(uri):
    client = get_mongo_connection(uri)
    if not client:
        return []

    databases = get_all_databases(client)
    yamls = []

    for db_name in databases:
        db = client[db_name]
        collections = get_all_collections(db)

        for collection_name in collections:
            collection = db[collection_name]
            schema = get_collection_schema(collection)
            dimensions = []

            for field, field_type in schema.items():
                column = {"name": field, "type": field_type}
                dimensions.append(column)

            yaml_structure = {
                "name": collection_name,
                "database": db_name,
                "dimensions": dimensions,
                "description": ""
            }

            print(f"YAML structure for collection '{collection_name}' in database '{db_name}': {yaml_structure}")
            yamls.append(yaml_structure)

    client.close()
    return yamls

if __name__ == "__main__":
    uri = "mongodb+srv://admin:1234Burger@codycluster.xullp6s.mongodb.net/?retryWrites=true&w=majority&appName=codycluster"
    yamls = mongo_to_yamls(uri)

    for yaml_doc in yamls:
        print(yaml.dump(yaml_doc, default_flow_style=False))