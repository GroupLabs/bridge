import openai
import json

openai.api_key = 'key'

# Load the function descriptions 
with open('src/services/services.json', 'r') as f:
    functions = json.load(f)

# Load the data descriptions 
with open('src/metadata/employees.csv.json', 'r') as f:
    data_description = json.load(f)

# Create a msg from data description
fields = [f"{field['field']} ({field['type']}): {field['description']}" for field in data_description['metadata']['metadata']]
data_message = f"I have a dataset named '{data_description['source_name']}' which includes the following fields: {', '.join(fields)}."

# Make API call
response = openai.ChatCompletion.create(
  model="gpt-3.5-turbo",
  messages=[
        {"role": "system", "content": "You are a helpful assistant that suggests functions based on the dataset."},
        {"role": "user", "content": data_message}
    ],
  functions=functions
)

# Print GPT suggested function
function_call = response['choices'][0]['message'].get('function_call')
if function_call:
    print(f"The suggested function is {function_call['name']}.")
else:
    print("No function suggestion found.")
