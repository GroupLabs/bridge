import os
from dotenv import load_dotenv

load_dotenv()

class config:
    # api
    ENV = str(os.getenv('ENV', 'DEBUG')) 
    PORT = int(os.getenv('API_PORT', 8000))

    # auto description
    OPENAI_KEY = os.getenv("OPENAI_API_KEY")

    # e5_small
    E5_SMALL_MAX_LEN = int(os.getenv('E5_SMALL_MAX_LEN', 512))

    # log
    LOG_LEVEL = str(os.getenv('LOG_LEVEL', 'INFO'))

    # ollama
    LLM_URL = str(os.getenv('LLM_URL', "http://localhost:11434/api/"))
    LLM_MODEL = str(os.getenv('LLM_MODEL', "llama3"))

    # storage
    CELERY_BROKER_URL = str(os.getenv('CELERY_BROKER_URL', "amqp://guest:guest@localhost"))

    # elasticutils
    ELASTIC_PASSWORD = str(os.getenv('ELASTIC_PASSWORD'))
    ELASTIC_CA_CERT_PATH = str(os.getenv('ELASTIC_CA_CERT_PATH', "/Users/noelthomas/Documents/GitHub/Bridge/http_ca.crt"))
    ELASTIC_USER = str(os.getenv('ELASTIC_USER', "elastic"))
    ELASTIC_URL = str(os.getenv('ELASTIC_URL', "https://localhost:9200"))

    TRITON_URL = str(os.getenv('TRITON_URL', "https://localhost:9000"))

    MODEL_REPOSITORY_PATH = str(os.getenv('MODEL_REPOSITORY_PATH', "./"))

