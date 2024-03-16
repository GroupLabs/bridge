import pandas as pd 
import numpy as np 
from vespa.package import Schema, Document, Field, StructField, FieldSet, ApplicationPackage, Component, Parameter, RankProfile, Function, FirstPhaseRanking, SecondPhaseRanking, Struct, Array

from vespa.deployment import VespaDocker

# Define the struct that represents the complex type
dimension_struct = Struct(
    name="dimension",
    fields=[
        Field(name="name", type="string"),
        Field(name="type", type="string"),
        Field(name="sql", type="string"),
        Field(name = "foreign_key", type = "tring"),
        Field(name = "primary_key", type = "tring")
    ]
)
   
yaml_schema = Schema(
            name="yamls",
            mode = "streaming",
            document=Document(
                fields=[
                    Field(name="id", type="string", indexing=["summary"]),
                    Field(name="name", type="string", indexing=["summary", "index"]),
                    Field(name="sql_name", type="string", indexing=["summary", "index"]),
                    Field(name="dimensions", type = "array<dimension>" ,indexing=["summary", "index"], struct_field=dimension_struct),
                    Field(name="joins", type="array<string>", indexing=["summary", "index"]),
                    Field(name="metadata", type="map<string,string>", indexing=["summary", "index"]),
                    Field(name="chunkno", type="int", indexing=["summary", "attribute"]),
                    Field(name="chunk", type="string", indexing=["summary", "index"]),

                    Field(name="embedding", type="tensor<bfloat16>(x[384])",
                        indexing=['"passage: " . (input name || "") . " " . (input chunk || "")', "embed e5", "attribute"],
                        attribute=["distance-metric: angular"],
                        is_document_field=False
                    ),

                    Field(name="colbert", type="tensor<int8>(dt{}, x[16])",
                        indexing=['(input name || "") . " " . (input chunk || "")', "embed colbert", "attribute"],
                        is_document_field=False
                    )
                ],
            ),
            fieldsets=[
                FieldSet(name = "default", fields = ["name", "chunk"])
            ],
            struct = [dimension_struct]
)

vespa_app_name = "yamls"
vespa_application_package = ApplicationPackage(
        name=vespa_app_name,
        schema=[yaml_schema],
        components=[
            Component(id="e5", type="hugging-face-embedder",
              parameters=[
                  Parameter("transformer-model", {"url": "https://huggingface.co/intfloat/e5-small-v2/resolve/main/model.onnx"}),
                  Parameter("tokenizer-model", {"url": "https://huggingface.co/intfloat/e5-small-v2/raw/main/tokenizer.json"})
              ]
            ),
            Component(id="colbert", type="colbert-embedder",
              parameters=[
                  Parameter("transformer-model", {"url": "https://huggingface.co/colbert-ir/colbertv2.0/resolve/main/model.onnx"}),
                  Parameter("tokenizer-model", {"url": "https://huggingface.co/colbert-ir/colbertv2.0/raw/main/tokenizer.json"})
              ]
            )
        ]
)

colbert = RankProfile(
    name="colbert",
    inputs=[
        ("query(q)", "tensor<float>(x[384])"),
        ("query(qt)", "tensor<float>(qt{}, x[128])")
        ],
    functions=[
        Function(
            name="unpack",
            expression="unpack_bits(attribute(colbert))"
        ),
        Function(
            name="cos_sim",
            expression="closeness(field, embedding)"
        ),
        Function(
            name="max_sim",
            expression="""
                sum(
                    reduce(
                        sum(
                            query(qt) * unpack() , x
                        ),
                        max, dt
                    ),
                    qt
                )
            """
        )
    ],
    first_phase=FirstPhaseRanking(
        expression="cos_sim"
    ),
    second_phase=SecondPhaseRanking(
        expression="max_sim"
    ),
    match_features=["max_sim", "cos_sim"]
)

yaml_schema.add_rank_profile(colbert)
vespa_application_package.to_files("VespaAppYamls-test")

vespa_container = VespaDocker()
vespa_connection = vespa_container.deploy(application_package=vespa_application_package)

import shutil
import os

# Your existing code to define the application package goes here...

# Define the directory where the application files will be written
application_dir = r'C:\Users\Eugene\Documents\GroupLabs\bridge\MySQL_Cubes_Nodes\VespaAppYamls\\'

# # Define the name for the zip file
zip_name = 'yamls-package'

# # Create the zip archive
shutil.make_archive(application_dir + zip_name, 'zip', application_dir)
