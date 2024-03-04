import pandas as pd 
import numpy as np 
from vespa.package import Schema, Document, Field, FieldSet, ApplicationPackage, Component, Parameter, RankProfile, Function, FirstPhaseRanking, SecondPhaseRanking

   
pdf_schema = Schema(
            name="pdf",
            mode = "streaming",
            document=Document(
                fields=[
                    Field(name="id", type="string", indexing=["summary"]),
                    Field(name="title", type="string", indexing=["summary", "index"]),
                    Field(name="url", type="string", indexing=["summary", "index"]),
                    Field(name="authors", type="array<string>", indexing=["summary", "index"]),
                    Field(name="metadata", type="map<string,string>", indexing=["summary", "index"]),
                    Field(name="page", type="int", indexing=["summary", "attribute"]),
                    Field(name="chunkno", type="int", indexing=["summary", "attribute"]),
                    Field(name="chunk", type="string", indexing=["summary", "index"]),

                    Field(name="embedding", type="tensor<bfloat16>(x[384])",
                        indexing=['"passage: " . (input title || "") . " " . (input chunk || "")', "embed e5", "attribute"],
                        attribute=["distance-metric: angular"],
                        is_document_field=False
                    ),

                    Field(name="colbert", type="tensor<int8>(dt{}, x[16])",
                        indexing=['(input title || "") . " " . (input chunk || "")', "embed colbert", "attribute"],
                        is_document_field=False
                    )
                ],
            ),
            fieldsets=[
                FieldSet(name = "default", fields = ["title", "chunk"])
            ]
)

vespa_app_name = "pdfs"
vespa_application_package = ApplicationPackage(
        name=vespa_app_name,
        schema=[pdf_schema],
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

pdf_schema.add_rank_profile(colbert)
vespa_application_package.to_files("VespaApp")


import shutil
import os

# Your existing code to define the application package goes here...

# Define the directory where the application files will be written
application_dir = r'C:\Users\Eugene\Documents\GroupLabs\bridge\MySQL_Cubes_Nodes\VespaApp\\'

# # Define the name for the zip file
zip_name = 'my_vespa_app_package'

# # Create the zip archive
shutil.make_archive(application_dir + zip_name, 'zip', application_dir)
