from vespa.package import Schema, Document, Field, FieldSet
from vespa.package import ApplicationPackage, Component, Parameter
from vespa.package import RankProfile, Function, FirstPhaseRanking, SecondPhaseRanking

from vespa.deployment import VespaDocker

VESPA_NAME = "search"
VESPA_APP_ROOT = "./search-config"

def create_config():

    # // text chunk
    # // unstructured
    # ID: oid // generated @ creation
    # Document ID: oid // generated @ document ingestion - ties all chunks in document together
    # Owner/Access Group: str // user defined
    # Chunk Text: str (max 256 char) // actual value
    # Chunking Strategy: str // useful meta
    # Chunk No: int // useful meta
    # Unstructured Embedding: Vec or Mat
    # Last Updated: datetime // sort parameter

    text_chunk_schema = Schema(
        name="text_chunk",
        document=Document(
            fields=[
                Field(name="id", type="string", indexing=["attribute", "summary"], attribute={"fast-search": True}),
                Field(name="document_id", type="string", indexing=["attribute", "summary"], attribute={"fast-search": True}),
                Field(name="access_group", type="string", indexing=["summary", "attribute"]),
                Field(name="chunk_text", type="string", indexing=["summary", "index"], index="enable-bm25", match=["text"], max_length=256),
                Field(name="chunking_strategy", type="string", indexing=["summary", "attribute"]),
                Field(name="chunk_no", type="int", indexing=["summary", "attribute"]),
                Field(name="embedding", type="tensor<double>(d0[128])", indexing=["attribute"]),
                Field(name="last_updated", type="long", indexing=["summary", "attribute"])
            ]
        ),
        fieldsets=[
                FieldSet(name = "default", fields = ["chunk_text", "access_group"])
            ],
        rank_profiles=[RankProfile(name="default", first_phase="nativeRank(chunk_text)")]
    )

    # // document is not ingestable
    # // unstructured
    # ID: oid // generated @ creation
    # Owner/Access Group: str // user defined
    # Description Text: str (max 256 char) // useful meta
    # File Path: str (validated) // useful meta
    # Unstructured Embedding: Vec or Mat // embedding
    # Last Updated: datetime // sort parameter
    # Data Hash: str // integrity check

    document_schema = Schema(
        name="document_meta",
        document=Document(
            fields=[
                Field(name="id", type="string", indexing=["attribute", "summary"], attribute={"fast-search": True}),
                Field(name="access_group", type="string", indexing=["summary", "attribute"]),
                Field(name="description_text", type="string", indexing=["summary", "index"], max_length=256),
                Field(name="file_path", type="string", indexing=["summary", "attribute"]),
                Field(name="embedding", type="tensor<double>(d0[128])", indexing=["attribute"]),
                Field(name="last_updated", type="long", indexing=["summary", "attribute"]),
                Field(name="data_hash", type="string", indexing=["summary", "attribute"])
            ]
        ),
        fieldsets=[
                FieldSet(name = "default", fields = ["description_text", "access_group"])
            ],
        rank_profiles=[RankProfile(name="default", first_phase="nativeRank(description_text)")]
    )

    # // table meta
    # // structured
    # ID: oid // generated @ creation
    # Database ID: oid // generated @ database ingestion - ties all tables in db together
    # Owner/Access Group: str // user defined
    # Description Text: str (max 256 char) // useful meta
    # Unstructured Embedding: Vec or Mat // embedding
    # Correlation Embedding: Vec or Mat // embedding
    # Last Updated: datetime // sort parameter
    # Data Hash: str (what about event stream data?) // integrity check

    table_schema = Schema(
        name="table_meta",
        document=Document(
            fields=[
                Field(name="id", type="string", indexing=["attribute", "summary"], attribute={"fast-search": True}),
                Field(name="database_id", type="string", indexing=["attribute", "summary"], attribute={"fast-search": True}),
                Field(name="access_group", type="string", indexing=["summary", "attribute"]),
                Field(name="description_text", type="string", indexing=["summary", "index"], max_length=256),
                Field(name="embedding", type="tensor<double>(d0[128])", indexing=["attribute"]),
                Field(name="correlation_embedding", type="tensor<double>(d0[128])", indexing=["attribute"]),
                Field(name="last_updated", type="long", indexing=["summary", "attribute"]),
                Field(name="data_hash", type="string", indexing=["summary", "attribute"])
            ]
        ),
        fieldsets=[
                FieldSet(name = "default", fields = ["description_text", "access_group"])
            ],
        rank_profiles=[RankProfile(name="default", first_phase="nativeRank(description_text)")]
    )

    vespa_app_name = "search"
    vespa_application_package = ApplicationPackage(
            name=vespa_app_name,
            schema=[text_chunk_schema, document_schema, table_schema]
    )

    vespa_application_package.to_files("search-config")

def create_vespa_container():

    VespaDocker().deploy_from_disk(
        application_name=VESPA_NAME, 
        application_root=VESPA_APP_ROOT
    )

if __name__ == "__main__":
    create_config()
    create_vespa_container()
    
