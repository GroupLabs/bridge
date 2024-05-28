from elasticutils import Search
from datetime import datetime

# Initialize the Elasticsearch instance
es = Search()

# Create a test document
test_document = {
    "file_type": "text/plain",
    "file_id": "testfile123",
    "file_name": "Test File",
    "file_description": "This is a test file",
    "file_size": 1234,
    "permissions": {
        "person": "user1",
        "permission": "read"
    },
    "last_modified_time": datetime.now().isoformat(),
    "created_time": datetime.now().isoformat()
}

# Insert the test document
es.insert_document(test_document, index="file_meta")

print("Test document inserted.")
