from transformers import TapexTokenizer, BartForConditionalGeneration
import pandas as pd

tokenizer1 = TapexTokenizer.from_pretrained("microsoft/tapex-large-finetuned-wikisql")
model1 = BartForConditionalGeneration.from_pretrained("microsoft/tapex-large-finetuned-wikisql")

from transformers import AutoTokenizer, AutoModelForTableQuestionAnswering

tokenizer = AutoTokenizer.from_pretrained("google/tapas-large-finetuned-wtq")

model = AutoModelForTableQuestionAnswering.from_pretrained("google/tapas-large-finetuned-wtq")


data = {
    "year": [1896, 1900, 1904, 2004, 2008, 2012],
    "city": ["athens", "paris", "st. louis", "athens", "beijing", "london"]
}
table = pd.DataFrame.from_dict(data)

# tapex accepts uncased input since it is pre-trained on the uncased corpus
query = "In which year did beijing host the Olympic Games?"
encoding = tokenizer(table=table, query=query, return_tensors="pt")

outputs = model.generate(**encoding)

print(tokenizer.batch_decode(outputs, skip_special_tokens=True))
# [' 2008.0']

while True:
    query = input("Enter a question: ")
    encoding = tokenizer(table=table, query=query, return_tensors="pt")

    outputs = model.generate(**encoding)

    print(tokenizer.batch_decode(outputs, skip_special_tokens=True))
    