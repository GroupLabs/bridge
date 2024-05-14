# colab file experimentation at https://colab.research.google.com/drive/1x_DILdesO7hQTaNHq7UZ_v9Yb7lXlrL_
#https://colab.research.google.com/drive/12gth2lxAJGsVKxzSIuh1fjVfXiB0ctpx?usp=sharing
#for usage, see the colab

#TO DO: 1. get fields from elasicsearch that decide flow of logic for the code
#       2. Add if __name__==__main__ part
#       3. Add padding or cut data if size is not compatible with config??

import re
import requests
import json
import torch
import numpy as np
import pprint as pp

#parsing the config file:
def parse_config_from_file(file_path):
    try:
        with open(file_path, 'r') as file:  # Added try-except for file operation
            text = file.read()
    except IOError as e:
        print(f"Error reading file {file_path}: {e}")
        return None  # Return None if file operation fails
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

#for nested lists:
def convert_to_tensor(data, dtype):
    """
    Convert a list, a nested list, or an empty list of data to a tensor with the specified dtype.
    If the data list is empty, return an appropriately shaped tensor of the given dtype with zero elements.
    """
    if data:  # Ensure there's data to convert
        if isinstance(data[0], list):  # Nested lists
            return torch.tensor(data, dtype=dtype)
        else:
            return torch.tensor([data], dtype=dtype)  # Single list, ensure it's nested for consistency
    else:
        return torch.tensor([], dtype=dtype).reshape(0)  # Return an empty tensor with no dimensions

#transforming inputs into the right type:
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

    for input_item in input_config:
        print(f"Input item: {input_item}")
        input_name = input_item['name']
        desired_dtype = dtype_mapping.get(input_item['data_type'], torch.float32)
        raw_data = data.get(input_name, [])
        print(f"Raw data: {raw_data}")

        # Convert data to the specified type
        tensor = convert_to_tensor(raw_data, desired_dtype)

        # Prepare dimensions specification
        if 'dims' in input_item and input_item['dims'][0] != '-1':
            dims = tuple(int(d) if isinstance(d, (str, int)) and str(d).isdigit() else -1 for d in input_item['dims'])
            if all(d != -1 for d in dims):
                tensor = tensor.view(*dims)
            else:
                raise ValueError(f"Dimension mismatch for {input_name}: cannot reshape array of size {tensor.numel()} into shape {tuple(dims)}")

        prepared_data[input_name] = tensor

    return prepared_data



"""Preparing to pass these arguments as input into the model:"""

def format_model_inputs(model_inputs, config):
    """
    Formats the model inputs as a structured dictionary for model deployment.
    If a dimension is set as '-1', the shape of the tensor will be kept as is.

    Args:
    model_inputs (dict): Dictionary containing tensors for each input.
    config (dict): Configuration dictionary that specifies how each input should be handled.
    This is returned by the parse_config method.

    Returns:
    dict: Structured data formatted for passing as model input.
    """
    formatted_inputs = {
        "inputs": []
    }

    input_config = config['input']

    for input_item in input_config:
        input_name = input_item['name']
        datatype = input_item['data_type'].replace('TYPE_', '')
        tensor = model_inputs.get(input_name, None)

        if tensor is None:
            print(f"Warning: No tensor found for input {input_name}")
            continue

        # Determine the shape based on the config
        if input_item['dims'] == ['-1']:  # If dimension is '-1', keep the current shape
            shape = list(tensor.shape)  # Use the current tensor shape
        else:
            # Calculate new shape, handling '-1' to infer dimension
            shape = [int(dim) if dim != '-1' else tensor.size(i) for i, dim in enumerate(input_item['dims'])]

        try:
            tensor = tensor.view(*shape)  # Attempt to reshape tensor
        except RuntimeError as e:
            print(f"Error: Failed to reshape tensor for {input_name}. Details: {e}")
            continue

        formatted_inputs["inputs"].append({
            "name": input_name,
            "datatype": datatype,
            "shape": shape,
            "data": tensor.tolist()  # Convert tensor data to list for JSON serialization
        })

    return formatted_inputs


#to pass the inputs to the model:
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




