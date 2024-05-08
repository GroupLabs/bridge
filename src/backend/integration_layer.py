# colab file experimentation at https://colab.research.google.com/drive/1x_DILdesO7hQTaNHq7UZ_v9Yb7lXlrL_
#https://colab.research.google.com/drive/12gth2lxAJGsVKxzSIuh1fjVfXiB0ctpx?usp=sharing
#for usage, see the colab


import re

#parsing the config file:
def parse_config_from_file(file_path):
    with open(file_path, 'r') as file:
        text = file.read()
    return parse_config(text)

def parse_config(text):
    def tokenize(text):
        # Use regex to split the text into meaningful tokens
        tokens = re.findall(r'[^\s"\'\[\]{},:]+|["\'][^"\']*["\']|\[|\]|\{|\}|,', text)
        return tokens

    def parse_value(tokens, cursor):
        if cursor >= len(tokens):
            return None, cursor  # Prevent out-of-range errors

        token = tokens[cursor]
        cursor += 1
        if token == '[':
            array = []
            while cursor < len(tokens) and tokens[cursor] != ']':
                if tokens[cursor] == ',':  # Skip commas directly within array parsing
                    cursor += 1
                    continue
                item, cursor = parse_value(tokens, cursor)
                if item is not None:
                    array.append(item)
            cursor += 1  # Move past the ']'
            return array, cursor
        elif token == '{':
            obj, cursor = parse_object(tokens, cursor)
            return obj, cursor
        elif token.isdigit():
            return int(token), cursor
        elif token.replace('.', '', 1).isdigit():
            return float(token), cursor
        elif token == 'true':
            return True, cursor
        elif token == 'false':
            return False, cursor
        else:
            return token.strip('"'), cursor

    def parse_object(tokens, cursor):
        obj = {}
        while cursor < len(tokens) and tokens[cursor] != '}':
            if tokens[cursor] == ',':
                cursor += 1  # Skip commas within objects
                continue
            key = tokens[cursor].strip(':').strip('"')
            cursor += 1
            if tokens[cursor] == ':':
                cursor += 1  # Skip the colon following the key
            value, cursor = parse_value(tokens, cursor)
            obj[key] = value
        cursor += 1  # Move past the '}'
        return obj, cursor

    tokens = tokenize(text)
    cursor = 0
    result, _ = parse_object(tokens, cursor)
    return result

"""Converting the data columns received by ES metadata mappings into 
right format for the model (according to config). This assumes ES mappings 
returns a dictionary for each input feature of the model, a key for column 
name and a value as a list of data points in that column. The code assumes 
that the values are a list of strings, ints, floats, bools..."""

import torch

def prepare_inputs_for_model(data, config):
    input_config = config.get('input', [])
    
    prepared_data = {}

    dtype_mapping = {
        'TYPE_INT8': torch.int8,
        'TYPE_UINT8': torch.uint8,
        'TYPE_INT16': torch.int16,
        'TYPE_INT32': torch.int32,
        'TYPE_INT64': torch.int64,
        'TYPE_FP16': torch.float16,
        'TYPE_FP32': torch.float32,
        'TYPE_FP64': torch.float64,
        'TYPE_COMPLEX32': torch.complex32,
        'TYPE_COMPLEX64': torch.complex64,
        'TYPE_COMPLEX128': torch.complex128,
        'TYPE_BOOL': torch.bool
    }

    # Iterate through all inputs specified in the configuration
    for input_item in input_config:
        
        if isinstance(input_item, dict):
            input_name = input_item['name']
            desired_dtype = dtype_mapping.get(input_item['data_type'], torch.float32)
            dims = tuple(int(d) if str(d).isdigit() else -1 for d in input_item['dims'])
            # Extract and convert the corresponding data column
            raw_data = data.get(input_name, [])        
            converted_data = []

            # Convert to the desired data type
            for x in raw_data:
                #print(x)
                try:
                    if 'int' in input_item['data_type'].lower():
                        converted_data.append(int(x))                      
                    elif 'fp' in input_item['data_type'].lower():
                        converted_data.append(float(x))        
                    elif 'bool' in input_item['data_type'].lower():
                        converted_data.append(bool(int(x)))
                    elif 'complex' in input_item['data_type'].lower():
                        # Assuming complex numbers are in the format "real_part imag_part"
                        real_part, imag_part = map(float, x.split())
                        converted_data.append(torch.complex(real_part, imag_part))
                except ValueError as e:
                    raise ValueError(f"Error converting {x} to {input_item['data_type']}: {e}")

            # Create a tensor and reshape it if dimensions are specified
            tensor = torch.tensor(converted_data, dtype=desired_dtype)
            if dims[0] != -1:
                print(tensor)
                tensor = tensor.reshape(dims)
            prepared_data[input_name] = tensor

    return prepared_data

"""Preparing to pass these arguments as input into the model:"""

import torch
import pprint as pp

def format_model_inputs(model_inputs, config):
    """
    Formats the model inputs as a structured dictionary for model deployment.

    Args:
    model_inputs (dict): Dictionary containing tensors for each input.
    config (dict): Configuration dictionary that specifies how each input should be handled.

    Returns:
    dict: Structured data formatted for passing as model input.
    """
    formatted_inputs = {
        "inputs": []
    }

    input_config = config['input']

    for input_item in input_config:
        if isinstance(input_item, dict):
            input_name = input_item['name']
            datatype = input_item['data_type'].replace('TYPE_', '')
            tensor = model_inputs[input_name]

            # Ensure tensor is in the correct shape
            desired_shape = input_item['dims']
            # Convert shape entries to integers where possible, handle the '-1' placeholder
            shape = [int(dim) if dim != '-1' else tensor.size(i) for i, dim in enumerate(desired_shape)]
            tensor = tensor.view(shape)

            formatted_inputs["inputs"].append({
                "name": input_name,
                "datatype": datatype,
                "shape": shape,
                "data": tensor.tolist()  # Convert tensor data to list for JSON serialization
            })

    return formatted_inputs

#to pass the inputs to the model:
import requests
import json

def make_inference_request(url, model_input, headers=None):
    # Define the request headers if not provided
    if headers is None:
        headers = {"Content-Type": "application/json"}
    
    # Define the request data
    request_data = json.dumps(model_input)
    
    # Make the request
    response = requests.post(url, headers=headers, data=request_data)
    
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the response
        result = response.json()
        # If you want to extract the output values:
        output = result["outputs"][0]["data"][0]
        return output
    else:
        # If the request failed, print the error message
        print(f"Error: {response.status_code} - {response.text}")
        return None




