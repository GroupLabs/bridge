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
    LLM_MODEL = str(os.getenv('LLM_MODEL', "mistral"))

    # storage
    VESPA_CONFIG_PATH = str(os.getenv('VESPA_CONFIG_PATH', "./search-config"))
    CELERY_BROKER_URL = str(os.getenv('VESPA_CONFIG_PATH', "amqp://guest:guest@localhost"))

    # vespautils
    VESPA_CONFIG_URL = str(os.getenv('VESPA_CONFIG_PATH', "http://localhost:19071/"))
    VESPA_PREPAREANDACTIVATE_ENDP = str(os.getenv('VESPA_PREPAREANDACTIVATE_ENDP', VESPA_CONFIG_URL + "application/v2/tenant/default/prepareandactivate"))
    VESPA_FEED_URL = str(os.getenv('VESPA_FEED_URL', "http://localhost:8080/"))
    VESPA_QUERY_URL = str(os.getenv('VESPA_QUERY_URL', "http://localhost:8082/"))