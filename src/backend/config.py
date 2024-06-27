import os
from dotenv import load_dotenv

load_dotenv()

class config:
    # api
    ENV = str(os.getenv('ENV', 'DEBUG')) 
    PORT = int(os.getenv('API_PORT', 8000))

    TEMP_DIR = "./tmp"

    # auto description
    OPENAI_KEY = os.getenv("OPENAI_KEY", "")

    # e5_small
    E5_SMALL_MAX_LEN = int(os.getenv('E5_SMALL_MAX_LEN', 512))

    # log
    LOG_LEVEL = str(os.getenv('LOG_LEVEL', 'INFO'))

    # ollama
    LLM_URL = str(os.getenv('LLM_URL', "https://api.openai.com/v1"))
    LLM_MODEL = str(os.getenv('LLM_MODEL', "gpt-4o")) #just change to gpt-4 when needed also change the .env

    # storage
    CELERY_BROKER_URL = str(os.getenv('CELERY_BROKER_URL', "amqp://guest:guest@localhost"))

    # elasticutils
    ELASTIC_PASSWORD = str(os.getenv('ELASTIC_PASSWORD'))
    ELASTIC_CA_CERT_PATH = str(os.getenv('ELASTIC_CA_CERT_PATH', "./http_ca.crt"))
    ELASTIC_USER = str(os.getenv('ELASTIC_USER', "elastic"))
    ELASTIC_URL = str(os.getenv('ELASTIC_URL', "https://localhost:9200"))

    TRITON_URL = str(os.getenv('TRITON_URL', "localhost:9000"))

    MODEL_REPOSITORY_PATH = str(os.getenv('MODEL_REPOSITORY_PATH', "./"))

    AZURE_CONNECTION_STRING = str(os.getenv('AZURE_CONNECTION_STRING', "x"))
    MODEL_CONTAINER_NAME = str(os.getenv('MODEL_CONTAINER_NAME', "x"))
    MODEL_SOURCE_FOLDER = str(os.getenv('MODEL_SOURCE_FOLDER', "x"))

    MLFLOW_TRACKING_URI="http://mlflow:5000"
