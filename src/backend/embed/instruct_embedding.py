import torch
import torch.nn.functional as F

from torch import Tensor
from transformers import AutoTokenizer, AutoModel

INSTRUCT_EMBEDDING_MODEL_NAME = 'Salesforce/SFR-Embedding-Mistral'
INSTRUCT_EMBEDDING_MODEL_MAX_LEN = 4096

def load_model_and_tokenizer(model_name='intfloat/e5-mistral-7b-instruct'):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    return tokenizer, model

tokenizer, model = load_model_and_tokenizer(INSTRUCT_EMBEDDING_MODEL_NAME)

def last_token_pool(last_hidden_states: Tensor,
                 attention_mask: Tensor) -> Tensor:
    left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])
    if left_padding:
        return last_hidden_states[:, -1]
    else:
        sequence_lengths = attention_mask.sum(dim=1) - 1
        batch_size = last_hidden_states.shape[0]
        return last_hidden_states[torch.arange(batch_size, device=last_hidden_states.device), sequence_lengths]

def get_detailed_instruct(task_description: str, query: str) -> str:
    return f'Instruct: {task_description}\nQuery: {query}'

def embed_query(task, query, max_length=INSTRUCT_EMBEDDING_MODEL_MAX_LEN):
    detailed_query = get_detailed_instruct(task, query)
    batch_dict = tokenizer(detailed_query, max_length=max_length - 1, return_attention_mask=True, padding=True, truncation=True, return_tensors='pt')
    outputs = model(**batch_dict)
    query_embeddings = last_token_pool(outputs.last_hidden_state, batch_dict['attention_mask'])
    return F.normalize(query_embeddings, p=2, dim=1)

def embed_document(document, max_length=INSTRUCT_EMBEDDING_MODEL_MAX_LEN):
    batch_dict = tokenizer(document, max_length=max_length - 1, return_attention_mask=True, padding=True, truncation=True, return_tensors='pt')
    outputs = model(**batch_dict)
    document_embeddings = last_token_pool(outputs.last_hidden_state, batch_dict['attention_mask'])
    return F.normalize(document_embeddings, p=2, dim=1)

def embed_queries(tasks, queries, max_length=INSTRUCT_EMBEDDING_MODEL_MAX_LEN):
    detailed_queries = [get_detailed_instruct(task, query) for task, query in zip(tasks, queries)]
    batch_dict = tokenizer(detailed_queries, max_length=max_length - 1, return_attention_mask=True, padding=True, truncation=True, return_tensors='pt')
    outputs = model(**batch_dict)
    query_embeddings = last_token_pool(outputs.last_hidden_state, batch_dict['attention_mask'])
    return F.normalize(query_embeddings, p=2, dim=1)

def embed_documents(documents, max_length=INSTRUCT_EMBEDDING_MODEL_MAX_LEN):
    batch_dict = tokenizer(documents, max_length=max_length - 1, return_attention_mask=True, padding=True, truncation=True, return_tensors='pt')
    outputs = model(**batch_dict)
    document_embeddings = last_token_pool(outputs.last_hidden_state, batch_dict['attention_mask'])
    return F.normalize(document_embeddings, p=2, dim=1)

embed_queries("What is Bridge?") # warmup

if __name__ == "__main__":
    tasks = [
        'Given a web search query, retrieve relevant passages that answer the query',
        'Given a web search query, retrieve relevant passages that answer the query'
    ]

    queries = [
        'how much protein should a female eat',
        'summit define'
    ]

    documents = [
        "As a general guideline, the CDC's average requirement of protein for women ages 19 to 70 is 46 grams per day...",
        "Definition of summit for English Language Learners. : 1 the highest point of a mountain : the top of a mountain..."
    ]

    query_embeddings = embed_queries(tasks, queries)
    document_embeddings = embed_documents(documents)


    a = embed_query(tasks[0], "Why is the sky blue?")
    b = embed_document("the sky is blue because of the sky.")

    print(a.shape)

    # To compute similarity scores
    scores = (query_embeddings @ document_embeddings.T) * 100
    print(scores.tolist())