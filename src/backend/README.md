This README is designed to give you the rundown. The backend consists of:

- Celery[RabbitMQ]
- Elasticsearch
- Triton (not implemented)
- Ollama (partially implemented)
- API
- Frontend (not implemented)

We want to use whatever is available that gets the job done. At least for now, no reinventing the wheel.

To get the API started in a containerized environment, use the following instructions:

0. Make sure you have the appropriate .env files! See [`bridge/src/deployment/.env.example`](https://github.com/GroupLabs/bridge/blob/main/src/deployment/.env.example) and run [`bridge/src/init_env.py`](https://github.com/GroupLabs/bridge/blob/main/src/init_env.py).
1. Start the docker-compose:

i. Switch to the deployment directory.

ii. Run: `docker-compose up -d`

> Note: This will start a few different containers, each are exposed to localhost. If you've never used ollama before, you may need to wait while it downloads an llm. Not sure if it will even download it by itself. The setup node should exit, and the console should indicate that all the processes have completed successfully. The Kibana container will look live on Docker Desktop, but it can take a while to get fully set up. However, you can start sending requests once the celery process in the api container is ready. When idling, the memory usage should be around 1.6GB. It should spin up to use all CPU resources under load.
>
> To see if it's up send a GET request to http://0.0.0.0:8000/health-check.

Use the following instructions to run everything locally (non-containerized):

To get the API started on your computer, do the following:

1. Ensure your Docker daemon is running. On Mac, just start Docker Desktop
2. In your venv (or not), run: `python --version` to find the version. The code is tested on 3.11 (stable), and 3.8 (experimental). Then run: `pip install magika FastAPI python-dotenv "unstructured[pdf]" pyvespa uvicorn requests celery httpx psycopg2-binary openai`
3. a. Run the following commands in order to start ES:

i. Create a network:
`docker network create elastic`

ii. Start a single node elastic-search:

```
docker run --name es01 --net elastic \
  -p 9200:9200 -p 9300:9300 \
  -e "discovery.type=single-node" \
  -e "xpack.license.self_generated.type: basic" \
  -t docker.elastic.co/elasticsearch/elasticsearch:8.13.0
```

This starts and configures an ES container with basic licensing. If you use another license, GL IS NOT LIABLE.

This will a produce a password, and an enrollment token. These will be useful in the next steps.

iii. Add the elastic password as an environment variable:
`export ELASTIC_PASSWORD=v4Ci+biLJx`

iv. Get the CA CERT:
`docker cp es01:/usr/share/elasticsearch/config/certs/http_ca.crt .`

This will download http_ca.crt to your current directory. Don't be alarmed, I don't think it's malware. It should help authenticate you to send requests to ES.

v. Everything you need to communicate with ES is now available. If you run into any issues refer to the documentation.

b. Follow these steps to start Kibana (optional):

i. Run the Kibana container in the same network:
`docker run --name kibana --net elastic -p 5601:5601 docker.elastic.co/kibana/kibana:8.13.0`

ii. Access the UI:
For some reason the URL that's generated in the Kibana logs does not take you to the UI.

Instead, try going to Docker Desktop, and hitting the '5601:5601' under the Port(s) column.

iii. Enter the Kibana enrollment token (remember I said it would be useful?).

iv. Enter your credentials:
username=elastic
password=generatedintheESlogs

v. You're ready to rock and roll!

4. Start RabbitMQ: `docker run -it --rm --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3.13-management` (this may download the image if you don't have it already)
5. Start Celery: `celery -A storage worker --loglevel=info -P threads` (unstructured is not fork-safe. use threads instead). Should be done in the backend dir.
6. Install poppler. On mac this is `brew install poppler`
7. Install tesseract. On mac this is `brew install tesseract`
8. Finally, run the API: `python api.py`

### Other fun stuff:

gives 10 threads, and 2 unique workers. task assignment is handled
celery -A storage worker --loglevel=info -P threads --concurrency=10 -n worker1@%h &
celery -A storage worker --loglevel=info -P threads --concurrency=10 -n worker2@%h &

---

To download punkt:

```
import nltk
import ssl

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

nltk.download()
```

---

### Misc:

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
