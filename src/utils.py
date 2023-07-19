import os
from dotenv import load_dotenv

import openai, pinecone

class PARAMS:

    prompts = {
        "code" : "You are a computer engineer that can only speak in code. Only return valid Python code. {query}. Express results in a matplotlib pyplot. Do not show the pyplot, instead save it as temp.png. Only return code. Store the answer in a variable named result.",
        
        "contextual-answer" : 
        
        '''You are a helpful AI assistant. Use the following pieces of context to answer the question at the end.
        If you don't know the answer, just say you don't know. DO NOT try to make up an answer.
        If the question is not related to the context, politely respond that you are tuned to only answer questions that are related to the context.
        Do not round numbers, only return the exact value.

        {context}

        Question: {query}
        Helpful answer:''',

        "metadata" : 
        
        '''Generate searchable metadata for the following CSV. Make it so that I can search for that metadata through a similarity search. Make the generated data include unique words about the CSV. {context}. Only return a JSON and nothing else.

        Use the following as an example of what the metadata should look like:
        "metadata": [
            {{
            "field": "first_name",
            "type": "string",
            "description": "The first name of the individual",
            }},
            {{
            "field": "last_name",
            "type": "string",
            "description": "The last name of the individual",
            }},
            {{
            "field": "email",
            "type": "string",
            "description": "The email address of the individual",
            }},
            {{
            "field": "make",
            "type": "string",
            "description": "The make of the vehicle the individual owns",
            }},
            {{
            "field": "title",
            "type": "string",
            "description": "The job title of the individual",
            }},
            {{
            "field": "salary",
            "type": "numeric",
            "description": "The salary of the individual",
            }}
        ]
        ''',
    }

    def __init__(self, DEBUG=False, EMBEDDING_MODEL="text-embedding-ada-002", BASIC_CHAT_MODEL="gpt-3.5-turbo", ADV_CHAT_MODEL="gpt-4-0613", LOGGING_ENABLED=False, LOGS_NAMESPACE='suncor-logs'):
        self.DEBUG = DEBUG
        self.EMBEDDING_MODEL = EMBEDDING_MODEL
        self.BASIC_CHAT_MODEL = BASIC_CHAT_MODEL
        self.ADV_CHAT_MODEL = ADV_CHAT_MODEL
        self.LOGGING_ENABLED = LOGGING_ENABLED
        if LOGGING_ENABLED:
            self.LOGS_NAMESPACE = LOGS_NAMESPACE
        else:
            self.LOGS_NAMESPACE = ""

def init_apis():
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

def log_question_answer(index, q_embedding, question, answer, _namespace):
    # create unique identifiers
    id = str(uuid.uuid4())

    # upsert a given question embedding into pinecone
    index.upsert(
        [(id, q_embedding, {'question':question, 'answer':answer})],
        namespace=_namespace
    )

    return {'namespace':_namespace, 'id':id}

def llm(prompt, model, role="user", stream=False):
    completion = openai.ChatCompletion.create(
    model=model,
    messages=[
        {"role": role, "content": prompt}
    ],
    temperature=0,
    stream=stream
    )

    result = {
        "content" : completion["choices"][0]["message"]["content"],
        "completion" : completion
    }

    return result

def vec_db(query, index, embedding_model):
    # search for similar documents
    xq = openai.Embedding.create(input=query, engine=embedding_model)['data'][0]['embedding']
    res = index.query([xq], top_k=4, include_metadata=True, namespace='suncor')

    # building context string
    context = ''

    for match in res['matches']:
        context='\n'.join([context, match.get('metadata').get('text')])

    return context

