import openai
import json

openai.api_key = 'key'

def predict_accident_probability(equipment_status):
    # placeholder
    if equipment_status == "poor":
        return "High"
    elif equipment_status == "average":
        return "Medium"
    else:
        return "Low"

functions = {
    "predict_accident_probability": predict_accident_probability
}

response = openai.ChatCompletion.create(
  model="gpt-3.5-turbo",
  messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": 'What is the accident probability if equipment status is "average" ?'}
    ],
  functions=[
        {
            "name": "predict_accident_probability",
            "description": "Predicts the accident probability based on equipment status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "equipment_status": {"type": "string"}
                },
                "required": ["equipment_status"]
            }
        }
    ]
)

function_call = response['choices'][0]['message'].get('function_call')
if function_call:
    function_name = function_call['name']
    arguments = json.loads(function_call['arguments'])

    if function_name in functions:
        result = functions[function_name](**arguments)
    else:
        result = "Function not recognized."
else:
    result = "No function call detected."

print(f"Accident probability is {result}")
