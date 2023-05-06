import os
from enum import Enum
from pydantic import BaseModel
from dotenv import load_dotenv

import openai, pinecone

class HealthCheckResponse(Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"

class Query(BaseModel):
    query: str
    streaming: bool

class PARAMS:
    # defining a prompt and a prompt template
    PROMPT_TEMPLATE = '''You are a helpful AI assistant. Use the following pieces of context to answer the question at the end.
    If you don't know the answer, just say you don't know. DO NOT try to make up an answer.
    If the question is not related to the context, politely respond that you are tuned to only answer questions that are related to the context.
    Do not round numbers, only return the exact value.

    {context}

    Question: {question}
    Helpful answer:'''

    def __init__(self, DEBUG=False, EMBEDDING_MODEL="text-embedding-ada-002", CHAT_MODEL="gpt-3.5-turbo", PROMPT_TEMPLATE=PROMPT_TEMPLATE, LOGGING_ENABLED=False, LOGS_NAMESPACE='suncor-logs'):
        self.DEBUG = DEBUG
        self.EMBEDDING_MODEL = EMBEDDING_MODEL
        self.CHAT_MODEL = CHAT_MODEL
        self.PROMPT_TEMPLATE = PROMPT_TEMPLATE
        self.LOGGING_ENABLED = LOGGING_ENABLED
        if LOGGING_ENABLED:
            self.LOGS_NAMESPACE = LOGS_NAMESPACE
        else:
            self.LOGS_NAMESPACE = ""

def init():
    load_dotenv('.env')

    # init openai
    openai.api_key = os.getenv("OPENAI_API_KEY")

    # init pinecone
    pinecone.init(
        api_key=os.getenv('PINECONE_API_KEY'),
        environment=os.getenv('PINECONE_ENV')  # find next to API key in console
    )

    if os.getenv('PINECONE_INDEX') is not None and os.getenv('PINECONE_INDEX').strip():
        return pinecone.Index(os.getenv('PINECONE_INDEX'))
    else:
        raise SystemError("Failed to initialize Pinecone index. Try checking your .env file.")

def request_chat(context, question, MODEL, prompt_template, role="user", stream=False):
    completion = openai.ChatCompletion.create(
    model=MODEL,
    messages=[
        {"role": role, "content": prompt_template.format(context=context, question=question)}
    ],
    temperature=0,
    stream=stream
    )

    return completion

def log_question_answer(index, q_embedding, question, answer, _namespace):
    # create unique identifiers
    id = str(uuid.uuid4())

    # upsert a given question embedding into pinecone
    index.upsert(
        [(id, q_embedding, {'question':question, 'answer':answer})],
        namespace=_namespace
    )

    return {'namespace':_namespace, 'id':id}

def retrieve_context(query, index, embedding_model):
    # search for similar documents
    xq = openai.Embedding.create(input=query, engine=embedding_model)['data'][0]['embedding']
    res = index.query([xq], top_k=4, include_metadata=True, namespace='suncor')

    # building context string
    context = ''

    for match in res['matches']:
        context='\n'.join([context, match.get('metadata').get('text')])

    return context

def retrieve_answer(query, index, chat_model, embedding_model, prompt_template, log=False, log_namespace=''):

    # search for similar documents
    xq = openai.Embedding.create(input=query, engine=embedding_model)['data'][0]['embedding']
    res = index.query([xq], top_k=4, include_metadata=True, namespace='suncor')

    # building context string
    context = ''

    for match in res['matches']:
        context='\n'.join([context, match.get('metadata').get('text')])

    answer = request_chat(context=context, question=query, MODEL=chat_model, prompt_template=prompt_template)["choices"][0]["message"]["content"]
    
    if log:
        if log_namespace == '':
            raise NameError("Log namespace is not defined.")
        log_question_answer(index, q_embedding=xq, question=query, answer=answer, _namespace=log_namespace)
    
    return answer