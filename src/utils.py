import os
from dotenv import load_dotenv

import openai, pinecone

class PARAMS:

    prompts = {
        "code" : '''You are a computer engineer that can only speak in code. Only return valid Python code. {query}. Express results in a matplotlib pyplot. Only return code. Store the answer in a variable named result.
        Use the following metadata:

        {
    "source_name": "data.csv",
    "type": "csv",
    "metadata": {
        "metadata": [
            {
                "field": "first_name",
                "type": "string",
                "description": "The first name of the individual",
                "unique_words": [
                    "first",
                    "name",
                    "individual"
                ]
            },
            {
                "field": "last_name",
                "type": "string",
                "description": "The last name of the individual",
                "unique_words": [
                    "last",
                    "name",
                    "individual"
                ]
            },
            {
                "field": "email",
                "type": "string",
                "description": "The email address of the individual",
                "unique_words": [
                    "email",
                    "address",
                    "individual"
                ]
            },
            {
                "field": "make",
                "type": "string",
                "description": "The make of the vehicle the individual owns",
                "unique_words": [
                    "make",
                    "vehicle",
                    "owns"
                ]
            },
            {
                "field": "title",
                "type": "string",
                "description": "The job title of the individual",
                "unique_words": [
                    "job",
                    "title",
                    "individual"
                ]
            },
            {
                "field": "salary",
                "type": "numeric",
                "description": "The salary of the individual",
                "unique_words": [
                    "salary",
                    "individual"
                ]
            }
        ]
    }
}

{
    "source_name": "equipment_status.csv",
    "type": "csv",
    "meta": {
        "metadata": [
            {
                "field": "Temperature",
                "type": "numeric",
                "description": "The recorded temperature"
            },
            {
                "field": "Humidity",
                "type": "numeric",
                "description": "The recorded humidity level"
            },
            {
                "field": "Wind Speed",
                "type": "numeric",
                "description": "The recorded wind speed"
            },
            {
                "field": "Equipment ID",
                "type": "string",
                "description": "The unique identifier for the equipment"
            },
            {
                "field": "Equipment Status",
                "type": "string",
                "description": "The current status of the equipment"
            },
            {
                "field": "Accident Occurred",
                "type": "boolean",
                "description": "Indicates whether an accident has occurred"
            }
        ]
    }
}
{
    "source_name": "oil_pipeline_accidents.csv",
    "type": "csv",
    "meta": {
        "metadata": [
            {
                "field": "Report Number",
                "type": "numeric",
                "description": "The unique number assigned to the accident report"
            },
            {
                "field": "Supplemental Number",
                "type": "numeric",
                "description": "Additional number related to the accident report"
            },
            {
                "field": "Accident Year",
                "type": "numeric",
                "description": "The year in which the accident occurred"
            },
            {
                "field": "Accident Date/Time",
                "type": "datetime",
                "description": "The exact date and time of the accident"
            },
            {
                "field": "Operator ID",
                "type": "numeric",
                "description": "Unique identifier for the operator of the pipeline"
            },
            {
                "field": "Operator Name",
                "type": "string",
                "description": "Name of the operator of the pipeline"
            },
            {
                "field": "Pipeline/Facility Name",
                "type": "string",
                "description": "Name of the pipeline or facility where the accident occurred"
            },
            {
                "field": "Pipeline Location",
                "type": "string",
                "description": "Location of the pipeline where the accident occurred"
            },
            {
                "field": "Pipeline Type",
                "type": "string",
                "description": "Type of the pipeline involved in the accident"
            },
            {
                "field": "Liquid Type",
                "type": "string",
                "description": "Type of liquid involved in the accident"
            },
            {
                "field": "Liquid Subtype",
                "type": "string",
                "description": "Subtype of the liquid involved in the accident"
            },
            {
                "field": "Liquid Name",
                "type": "string",
                "description": "Specific name of the liquid involved in the accident"
            },
            {
                "field": "Accident City",
                "type": "string",
                "description": "City where the accident occurred"
            },
            {
                "field": "Accident County",
                "type": "string",
                "description": "County where the accident occurred"
            },
            {
                "field": "Accident State",
                "type": "string",
                "description": "State where the accident occurred"
            },
            {
                "field": "Accident Latitude",
                "type": "numeric",
                "description": "Latitude coordinate of the accident location"
            },
            {
                "field": "Accident Longitude",
                "type": "numeric",
                "description": "Longitude coordinate of the accident location"
            },
            {
                "field": "Cause Category",
                "type": "string",
                "description": "General category of the cause of the accident"
            },
            {
                "field": "Cause Subcategory",
                "type": "string",
                "description": "Specific subcategory of the cause of the accident"
            },
            {
                "field": "Unintentional Release (Barrels)",
                "type": "numeric",
                "description": "Amount of liquid unintentionally released during the accident, measured in barrels"
            },
            {
                "field": "Intentional Release (Barrels)",
                "type": "numeric",
                "description": "Amount of liquid intentionally released during the accident, measured in barrels"
            },
            {
                "field": "Liquid Recovery (Barrels)",
                "type": "numeric",
                "description": "Amount of liquid recovered after the accident, measured in barrels"
            },
            {
                "field": "Net Loss (Barrels)",
                "type": "numeric",
                "description": "Net amount of liquid lost in the accident, measured in barrels"
            },
            {
                "field": "Liquid Ignition",
                "type": "string",
                "description": "Indicates whether the liquid ignited during the accident"
            },
            {
                "field": "Liquid Explosion",
                "type": "string",
                "description": "Indicates whether an explosion occurred during the accident"
            },
            {
                "field": "Pipeline Shutdown",
                "type": "string",
                "description": "Indicates whether the pipeline was shut down as a result of the accident"
            },
            {
                "field": "Shutdown Date/Time",
                "type": "datetime",
                "description": "Date and time when the pipeline was shut down"
            },
            {
                "field": "Restart Date/Time",
                "type": "datetime",
                "description": "Date and time when the pipeline was restarted"
            },
            {
                "field": "Public Evacuations",
                "type": "numeric",
                "description": "Number of public evacuations caused by the accident"
            },
            {
                "field": "Operator Employee Injuries",
                "type": "numeric",
                "description": "Number of injuries to operator employees caused by the accident"
            },
            {
                "field": "Operator Contractor Injuries",
                "type": "numeric",
                "description": "Number of injuries to operator contractors caused by the accident"
            },
            {
                "field": "Emergency Responder Injuries",
                "type": "numeric",
                "description": "Number of injuries to emergency responders caused by the accident"
            },
            {
                "field": "Other Injuries",
                "type": "numeric",
                "description": "Number of other injuries caused by the accident"
            },
            {
                "field": "Public Injuries",
                "type": "numeric",
                "description": "Number of injuries to the public caused by the accident"
            },
            {
                "field": "All Injuries",
                "type": "numeric",
                "description": "Total number of injuries caused by the accident"
            },
            {
                "field": "Operator Employee Fatalities",
                "type": "numeric",
                "description": "Number of fatalities to operator employees caused by the accident"
            },
            {
                "field": "Operator Contractor Fatalities",
                "type": "numeric",
                "description": "Number of fatalities to operator contractors caused by the accident"
            },
            {
                "field": "Emergency Responder Fatalities",
                "type": "numeric",
                "description": "Number of fatalities to emergency responders caused by the accident"
            },
            {
                "field": "Other Fatalities",
                "type": "numeric",
                "description": "Number of other fatalities caused by the accident"
            },
            {
                "field": "Public Fatalities",
                "type": "numeric",
                "description": "Number of fatalities to the public caused by the accident"
            },
            {
                "field": "All Fatalities",
                "type": "numeric",
                "description": "Total number of fatalities caused by the accident"
            },
            {
                "field": "Property Damage Costs",
                "type": "numeric",
                "description": "Costs associated with property damage caused by the accident"
            },
            {
                "field": "Lost Commodity Costs",
                "type": "numeric",
                "description": "Costs associated with the commodity lost in the accident"
            },
            {
                "field": "Public/Private Property Damage Costs",
                "type": "numeric",
                "description": "Costs associated with damage to public or private property caused by the accident"
            },
            {
                "field": "Emergency Response Costs",
                "type": "numeric",
                "description": "Costs associated with the emergency response to the accident"
            },
            {
                "field": "Environmental Remediation Costs",
                "type": "numeric",
                "description": "Costs associated with environmental remediation due to the accident"
            },
            {
                "field": "Other Costs",
                "type": "numeric",
                "description": "Other costs associated with the accident"
            },
            {
                "field": "All Costs",
                "type": "numeric",
                "description": "Total costs associated with the accident"
            }
        ]
    }
}
        ''',
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

    def __init__(self, DEBUG=False, EMBEDDING_MODEL="text-embedding-ada-002", BASIC_CHAT_MODEL="gpt-3.5-turbo", ADV_CHAT_MODEL="gpt-4", LOGGING_ENABLED=False, LOGS_NAMESPACE='suncor-logs'):
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
    prompt = prompt.replace('\u201c', '"').replace('\u201d', '"')

    print("HELLOOO|N|N|N|N|\n\n\n\n\n")
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

def vec_db(query, index, embedding_model, ns='suncor'):
    # search for similar documents
    xq = openai.Embedding.create(input=query, engine=embedding_model)['data'][0]['embedding']
    res = index.query([xq], top_k=4, include_metadata=True, namespace=ns)

    # building context string
    context = ''

    for match in res['matches']:
        context='\n'.join([context, match.get('metadata').get('text')])

    return context

