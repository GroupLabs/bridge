from vespa.package import Schema, Document, Field, FieldSet
from vespa.package import ApplicationPackage, Component, Parameter
from vespa.package import RankProfile, Function, FirstPhaseRanking, SecondPhaseRanking

def create_config():
    
    chunk_schema = Schema(
                    name="chunk",
                    mode="streaming",
                    document=Document(
                        fields=[
                            Field(name="id", type="string", indexing=["summary"]),
                            Field(name="title", type="string", indexing=["summary", "index"]),
                            Field(name="url", type="string", indexing=["summary", "index"]),
                            Field(name="authors", type="array<string>", indexing=["summary", "index"]),
                            Field(name="metadata", type="map<string,string>", indexing=["summary", "index"]),
                            Field(name="page", type="int", indexing=["summary", "attribute"]),
                            Field(name="chunkno", type="int", indexing=["summary", "attribute"]),
                            Field(name="chunk_text", type="string", indexing=["summary", "index"]),

                            Field(name="embedding", type="tensor<bfloat16>(x[384])",
                                indexing=['"passage: " . (input title || "") . " " . (input chunk_text || "")', "embed e5", "attribute"],
                                attribute=["distance-metric: angular"],
                                is_document_field=False
                            ),

                            Field(name="colbert", type="tensor<int8>(dt{}, x[16])",
                                indexing=['(input title || "") . " " . (input chunk_text || "")', "embed colbert", "attribute"],
                                is_document_field=False
                            )
                        ],
                    ),
                    fieldsets=[
                        FieldSet(name = "default", fields = ["title", "chunk_text"])
                    ]
    )

    vespa_application_package = ApplicationPackage(
            name="search",
            schema=[chunk_schema],
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

    chunk_schema.add_rank_profile(colbert)

    vespa_application_package.to_files("search-config")

if __name__ == "__main__":
    create_config()
