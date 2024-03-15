import torch.nn.functional as F

from torch import Tensor
from transformers import AutoTokenizer, AutoModel

E5_SMALL_MAX_LEN = 512

def average_pool(last_hidden_states: Tensor,
                 attention_mask: Tensor) -> Tensor:
    last_hidden = last_hidden_states.masked_fill(~attention_mask[..., None].bool(), 0.0)
    return last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]

tokenizer = AutoTokenizer.from_pretrained('intfloat/e5-small-v2')
model = AutoModel.from_pretrained('intfloat/e5-small-v2')

def embed_query(query, max_len=E5_SMALL_MAX_LEN):
    input_text = "query: " + query
    batch_dict = tokenizer(input_text, max_length=max_len, padding=True, truncation=True, return_tensors='pt')
    outputs = model(**batch_dict)
    return average_pool(outputs.last_hidden_state, batch_dict['attention_mask'])

def embed_passage(passage, max_len=E5_SMALL_MAX_LEN):
    input_text = "passage: " + passage
    batch_dict = tokenizer(input_text, max_length=max_len, padding=True, truncation=True, return_tensors='pt')
    outputs = model(**batch_dict)
    return average_pool(outputs.last_hidden_state, batch_dict['attention_mask'])


if __name__ == "__main__":

    # Each input text should start with "query: " or "passage: ".
    # For tasks other than retrieval, you can simply use the "query: " prefix.
    input_texts = ['query: how much protein should a female eat',
                'query: summit define',
                "passage: As a general guideline, the CDC's average requirement of protein for women ages 19 to 70 is 46 grams per day. But, as you can see from this chart, you'll need to increase that if you're expecting or training for a marathon. Check out the chart below to see how much protein you should be eating each day.",
                "passage: Definition of summit for English Language Learners. : 1  the highest point of a mountain : the top of a mountain. : 2  the highest level. : 3  a meeting or series of meetings between the leaders of two or more governments."]

    embeddings = [embed_query(x.split(": ")[1]) for x in input_texts[:1]] + [embed_passage(x.split(": ")[1]) for x in input_texts[1:]]
    embeddings = [F.normalize(embedding, p=2, dim=1) for embedding in embeddings]

    scores = embeddings[0] * embeddings[-1]
    print(scores.tolist())
