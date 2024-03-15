Deps

ensure docker daemon is running

pip install magika FastAPI python-dotenv "unstructured[pdf]" pyvespa uvicorn requests celery httpx

run the vespautils file to get the config

start rabbitmq
docker run -it --rm --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3.13-management

unstructured is not fork-safe. use threads instead
celery -A storage worker --loglevel=info -P threads

run: python api.py



Other:

gives 10 threads, and 2 unique workers. task assignment is handled
celery -A storage worker --loglevel=info -P threads --concurrency=10 -n worker1@%h &
celery -A storage worker --loglevel=info -P threads --concurrency=10 -n worker2@%h &


Stack:
- Celery[RabbitMQ]
- Vespa
- Triton
- Ollama
- API
- Frontend


“What information is important?”

1. Ingest
    - File type with Magika: https://opensource.googleblog.com/2024/02/magika-ai-powered-fast-and-efficient-file-type-identification.html?m=1
    - https://x.com/mayfer/status/1754077677286502600?s=46&t=C-lAPJA8zJecpJNV1n8ILg
    - Databse client: https://harlequin.sh
    - SuryaOCR
    - LlamaParser
    - https://x.com/austinbv/status/1762782262096179532?s=46&t=C-lAPJA8zJecpJNV1n8ILg 
    - Unstructured I/O
    - Goal: Ingest a data lake
2. Graph
    - https://moj-analytical-services.github.io/splink/
    - DuckDB
        - https://github.com/davidgasquez/awesome-duckdb
        - https://homepages.cwi.nl/~boncz/msc/2023-Wu.pdf
3. Search
    - https://github.com/lancedb/lance/tree/main
    - https://github.com/google/gemma.cpp 
4. Correlation/Causality
    - https://github.com/salesforce/PyRCA
    - https://github.com/py-why/dowhy
    - Correlation based embedding??? (https://chat.openai.com/share/19727edf-455e-4c60-84b3-9c6e019730c7)
    - https://x.com/mit_csail/status/1762894630020870404?s=46&t=C-lAPJA8zJecpJNV1n8ILg
    - https://github.com/SkalskiP/awesome-foundation-and-multimodal-models 
    - https://arxiv.org/abs/2212.09410
5. Present
    - https://evidence.dev
    - https://uwdata.github.io/mosaic/examples/
    - https://superset.apache.org
    - https://github.com/danswer-ai/danswer/tree/main
    - https://github.com/ankane/blazer?tab=readme-ov-file
    - https://www.metabase.com/
6. Other
    - Monitoring & Security: https://www.iceburst.io
    - Example: https://github.com/matsonj/nba-monte-carlo
    - Pgvector
    - ParadeDb
    - https://x.com/dwarkesh_sp/status/1762872471479529522?s=46&t=C-lAPJA8zJecpJNV1n8ILg
    - LanceDB