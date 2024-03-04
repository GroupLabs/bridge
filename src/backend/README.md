Deps

ensure docker daemon is running

pip install magika FastAPI python-dotenv "unstructured[pdf]" pyvespa uvicorn requests celery

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
