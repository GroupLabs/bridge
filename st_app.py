import streamlit as st
from src.utils import PARAMS, init_apis, vec_db, llm, log_question_answer
from st_model_utils import forecast_daily_accidents_model, forecast_daily_accidents_model_components, equipment_status_classifier
import openai, os
import json

openai.api_key = os.environ.get('OPENAI_API_KEY')

st.title('Bridge Capabilities Demonstration')

params = PARAMS() # init parameters
index = init_apis() # initialize openai and pinecone connections

data_type = st.selectbox(
    'Demonstrate capabilities for:',
    ('Docs', 'Data Tables', 'Models'))

with st.sidebar:
    st.header('Examples')
    st.divider()
    st.write('Here are some examples of questions you can ask the Bridge API.')

    if data_type == 'Docs':
        st.write('What was the comparable EBITDA in the first quarter of 2023?')
        st.write('What were segmented earnings in 2022 and 2023? What was the comparable EBITDA in the first quarter of 2023? How much was this up from last year?')
        
        st.write('What color is a Ford Focus?')

    if data_type == 'Data Tables':
        st.write('Find the top 10 most paid employee titles on average.')
        st.write('How many accidents occurred in 2015, 2016, and 2017?')
        st.write('Which facility incurred the most accidents? Return the top 5.')

    if data_type == 'Models':
        st.write('Forecast the next 100 days of daily accidents.')

st.write('This is a demonstration of the capabilities of the Bridge API. The Bridge API is a RESTful API that allows you to access data from the Bridge data engine.')

user_input = st.text_input("Enter message")

if user_input:
    if data_type == 'Docs':
        # find context
        context = vec_db(query=user_input, index=index, embedding_model=params.EMBEDDING_MODEL, ns='tc-demo')

        # build prompt
        prompt = params.prompts["contextual-answer"].format(context=context, query=user_input)

        # llm to generate answer
        contextual_answer = llm(prompt=prompt, model=params.ADV_CHAT_MODEL)["content"]

        st.write(contextual_answer)

    if data_type == 'Data Tables':

        plain_english = st.checkbox('Explain how the answer is generated in English please!')  

        prompt = f'''You are a computer engineer that can only speak in code. Only return valid Python code. {user_input}. Express results in a matplotlib pyplot. Store the plot in a variable named 'plot'. Do not show the plot. Only return code.'''
        
        employees_metadata = '''

        {
            "source_name": "employees.csv",
            "type": "csv",
            "metadata": {
                "metadata": [
                    {
                        "field": "first_name",
                        "type": "string",                    },
                    {
                        "field": "last_name",
                        "type": "string",                    },
                    {
                        "field": "email",
                        "type": "string",                    },
                    {
                        "field": "make",
                        "type": "string",                    },
                    {
                        "field": "title",
                        "type": "string",                    },
                    {
                        "field": "salary",
                        "type": "numeric",                    }
                ]
            }
        }'''

        equipment_status_metadata = '''
        {
            "source_name": "equipment_status.csv",
            "type": "csv",
            "meta": {
                "metadata": [
                    {
                        "field": "Temperature",
                        "type": "numeric",                    },
                    {
                        "field": "Humidity",
                        "type": "numeric",                    },
                    {
                        "field": "Wind Speed",
                        "type": "numeric",                    },
                    {
                        "field": "Equipment ID",
                        "type": "string",                    },
                    {
                        "field": "Equipment Status",
                        "type": "string",                    },
                    {
                        "field": "Accident Occurred",
                        "type": "boolean",                    }
                ]
            }
        }'''

        accidents_metadata = '''
        {
            "source_name": "oil_pipeline_accidents.csv",
            "type": "csv",
            "meta": {
                "metadata": [
                    {
                        "field": "Report Number",
                        "type": "numeric",                    },
                    {
                        "field": "Supplemental Number",
                        "type": "numeric",                    },
                    {
                        "field": "Accident Year",
                        "type": "numeric",                    },
                    {
                        "field": "Accident Date/Time",
                        "type": "datetime",                    },
                    {
                        "field": "Operator ID",
                        "type": "numeric",                    },
                    {
                        "field": "Operator Name",
                        "type": "string",                    },
                    {
                        "field": "Pipeline/Facility Name",
                        "type": "string",                    },
                    {
                        "field": "Pipeline Location",
                        "type": "string",                    },
                    {
                        "field": "Pipeline Type",
                        "type": "string",                    },
                    {
                        "field": "Liquid Type",
                        "type": "string",                    },
                    {
                        "field": "Liquid Subtype",
                        "type": "string",                    },
                    {
                        "field": "Liquid Name",
                        "type": "string",                    },
                    {
                        "field": "Accident City",
                        "type": "string",                    },
                    {
                        "field": "Accident County",
                        "type": "string",                    },
                    {
                        "field": "Accident State",
                        "type": "string",                    },
                    {
                        "field": "Accident Latitude",
                        "type": "numeric",                    },
                    {
                        "field": "Accident Longitude",
                        "type": "numeric",                    },
                    {
                        "field": "Cause Category",
                        "type": "string",                    },
                    {
                        "field": "Cause Subcategory",
                        "type": "string",                    },
                    {
                        "field": "Unintentional Release (Barrels)",
                        "type": "numeric",                    },
                    {
                        "field": "Intentional Release (Barrels)",
                        "type": "numeric",                    },
                    {
                        "field": "Liquid Recovery (Barrels)",
                        "type": "numeric",                    },
                    {
                        "field": "Net Loss (Barrels)",
                        "type": "numeric",                    },
                    {
                        "field": "Liquid Ignition",
                        "type": "string",                    },
                    {
                        "field": "Liquid Explosion",
                        "type": "string",                    },
                    {
                        "field": "Pipeline Shutdown",
                        "type": "string",                    },
                    {
                        "field": "Shutdown Date/Time",
                        "type": "datetime",                    },
                    {
                        "field": "Restart Date/Time",
                        "type": "datetime",                    },
                    {
                        "field": "Public Evacuations",
                        "type": "numeric",                    },
                    {
                        "field": "Operator Employee Injuries",
                        "type": "numeric",                    },
                    {
                        "field": "Operator Contractor Injuries",
                        "type": "numeric",                    },
                    {
                        "field": "Emergency Responder Injuries",
                        "type": "numeric",                    },
                    {
                        "field": "Other Injuries",
                        "type": "numeric",                    },
                    {
                        "field": "Public Injuries",
                        "type": "numeric",                    },
                    {
                        "field": "All Injuries",
                        "type": "numeric",                    },
                    {
                        "field": "Operator Employee Fatalities",
                        "type": "numeric",                    },
                    {
                        "field": "Operator Contractor Fatalities",
                        "type": "numeric",                    },
                    {
                        "field": "Emergency Responder Fatalities",
                        "type": "numeric",                    },
                    {
                        "field": "Other Fatalities",
                        "type": "numeric",                    },
                    {
                        "field": "Public Fatalities",
                        "type": "numeric",                    },
                    {
                        "field": "All Fatalities",
                        "type": "numeric",                    },
                    {
                        "field": "Property Damage Costs",
                        "type": "numeric",                    },
                    {
                        "field": "Lost Commodity Costs",
                        "type": "numeric",                    },
                    {
                        "field": "Public/Private Property Damage Costs",
                        "type": "numeric",                    },
                    {
                        "field": "Emergency Response Costs",
                        "type": "numeric",                    },
                    {
                        "field": "Environmental Remediation Costs",
                        "type": "numeric",                    },
                    {
                        "field": "Other Costs",
                        "type": "numeric",                    },
                    {
                        "field": "All Costs",
                        "type": "numeric",                    }
                ]
            }
        }'''

        # build prompt
        # prompt = params.prompts["code"].format(query=user_input)

        if "accident" in user_input.lower():
            prompt = prompt + accidents_metadata
            st.code("Using accidents data...")
        if "equipment" in user_input.lower():
            prompt = prompt + equipment_status_metadata
            st.code("Using equipment status data...")
        if "employee" in user_input.lower():
            prompt = prompt + employees_metadata
            st.code("Using employees data...")

        # generate code
        generated_code = llm(prompt=prompt, model=params.ADV_CHAT_MODEL)["content"]
        
        # clean up generated code
        split_text = generated_code.split("```") # split the generated code by ```
        split_text = split_text[1] if len(split_text) > 1 else "" # extract code string from surrounding ```
        code = split_text.lstrip("`").rstrip("`").lstrip("python") # remove ``` from beginning and end of generated code

        # print(code)

        # execute code
        try:
            exec(code, globals(), locals())
        except Exception as e:
            st.error(e)

        if "result" in locals():
            result = locals()['result']
        else:
            result = "No result variable returned."

        if "plot" in locals():
            plot = locals()['plot']
            st.pyplot(plot)
        else:
            result = "No result variable returned."

        if plain_english:
            st.write("Here's how the answer was generated:")
            st.write(llm(prompt="Please translate the code to simple english. Explain what was done. Do not explain each line of code: " + code, model=params.ADV_CHAT_MODEL)["content"])
        st.code(code)




    if data_type == "Models":
        functions = {
            "forecast_daily_accidents_model": forecast_daily_accidents_model,
            "forecast_daily_accidents_model_components": forecast_daily_accidents_model_components,
            "equipment_status_classifier": equipment_status_classifier
        }

        response = openai.ChatCompletion.create(
            model=params.ADV_CHAT_MODEL,
            messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": user_input}
                ],
            functions=[
                    {
                        "name": "forecast_daily_accidents_model",
                        "description": "Forecasts the number of accidents based on the input number of days into the future.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "days_into_future": {"type": "integer", "description": "The number of days into the future to forecast the number of accidents."}
                            },
                            "required": ["days_into_future"]
                        }
                    },
                    {
                        "name": "forecast_daily_accidents_model_components",
                        "description": "Forecasts the number of accidents based on the input number of days into the future. Shows the components.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "days_into_future": {"type": "integer", "description": "The number of days into the future to forecast the number of accidents."}
                            },
                            "required": ["days_into_future"]
                        }
                    },
                    {
                        "name": "equipment_status_classifier",
                        "description": "Classifies if an accident is likely to occure based on the conditions of the equipment.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "t": {"type": "integer", "description": "The temperature of the equipment."},
                                "h": {"type": "integer", "description": "The humidity of the equipment."},
                                "w": {"type": "integer", "description": "The wind speed of the equipment."},
                                "eid": {"type": "integer", "description": "The equipment ID of the equipment."},
                                "es": {"type": "integer", "description": "The equipment status of the equipment."}
                            },
                            "required": ["t","h","w","eid","es"]
                        }
                    },
                ]
            )

        st.code(response)

        function_call = response['choices'][0]['message'].get('function_call')
        if function_call:
            function_name = function_call['name']
            arguments = json.loads(function_call['arguments'])

            if function_name in functions:
                result = functions[function_name](**arguments)
            else:
                result = "Function not recognized."
        else:
            result = response['choices'][0]['message']['content']

        st.write(result)