# https://github.com/triton-inference-server/client/tree/main/src/python/examples
# Installation issues: https://github.com/triton-inference-server/server/issues/3603
# Model repo: https://github.com/triton-inference-server/server/blob/main/docs/user_guide/model_repository.md#repository-layout

import os
import tritonclient.http as httpclient
from tritonclient.utils import InferenceServerException # for custom error handling later
from log import setup_logger
import numpy as np
from config import config
from azure.storage.blob import ContainerClient, BlobType

from time import sleep # TODO remove this

# logger
logger = setup_logger("triton")

class TritonClient:

    # tritonclient has the following methods
    # get_model_repository_index(): Get a list of models that exist in the repository (does not mean ready for inference)
    # load_model(model_name): Load the model by name, so it's ready for inference
    # load_model(model_name, config): Can update config
    # load_model(model_name, config, files): Can update files
    # unload_model(model_name): Unload model
    # is_model_ready(model_name): Check if the model is ready for inference

    # BEWARE: not all operations onn Triton are blocking. This can lead to race conditions if not careful.
    # This is especially dangerous during model loading/unloading

    def __init__(
            self, 
            url=config.TRITON_URL, 
            verbose=1
            ):
        self.triton_client = httpclient.InferenceServerClient(
            url=url, verbose=verbose
        )

        if self.triton_client.is_server_ready():
            logger.info("Triton is available")
        else:
            logger.info("Triton is not available")
            logger.info(config.TRITON_URL)


    def add_model(self, model_path, config_path):

        model_name, extension = os.path.splitext(os.path.basename(model_path))

        logger.info(f"Model name: {model_name}")
    
        existing_models = self.triton_client.get_model_repository_index()

        if model_name in existing_models:
            logger.warn(f"Model '{model_name}' already exists.")
            return
        
        # create the appropriate file structure
        base_path = os.path.join(config.TEMP_DIR, "modeltmp", model_name)
        logger.info(base_path)
        version_path = os.path.join(base_path, str(1))
        logger.info(version_path)
        os.makedirs(version_path, exist_ok=True)

        # Move and rename model file to the version directory
        model_destination = os.path.join(version_path, f"model.{extension}")
        os.rename(model_path, model_destination)

        # Move and rename config file to the model directory
        config_destination = os.path.join(base_path, "config.pbtxt")
        os.rename(config_path, config_destination)

        # upload to model repository
        _upload(base_path, config.AZURE_CONNECTION_STRING, config.MODEL_CONTAINER_NAME)

        logger.info(f"Successfully added model to /modeltmp")

        sleep(30) # wait before loading model
        self.triton_client.load_model(model_name)

        # verify
        if self.triton_client.is_model_ready(model_name):
            logger.info(f"{model_name} is ready")
        else:
            logger.info(f"{model_name} is not ready")

    def test_infer(self,
        model_name,
        input_ids_data,
        attention_mask_data,
        headers=None,
        request_compression_algorithm=None,
        response_compression_algorithm=None,
    ):
        logger.info(f"Starting to POST request") 
        inputs = []
        outputs = []

        # Update input names, shapes, and datatypes
        input_ids = httpclient.InferInput("input_ids", [1, 14], "INT64")
        attention_mask = httpclient.InferInput("attention_mask", [1, 14], "FP32")

        # Convert lists to numpy arrays with correct datatype
        input_ids.set_data_from_numpy(np.array(input_ids_data, dtype=np.int64), binary_data=True)
        attention_mask.set_data_from_numpy(np.array(attention_mask_data, dtype=np.float32), binary_data=True)

        inputs.append(input_ids)
        inputs.append(attention_mask)

        # Request outputs
        outputs.append(httpclient.InferRequestedOutput("output", binary_data=False))        

        # Send inference request
        query_params = {"test_1": 1, "test_2": 2}
        results = self.triton_client.infer(
            model_name,
            inputs,
            outputs=outputs,
            query_params=query_params,
            headers=None,  # Ensure headers are set correctly if needed
            request_compression_algorithm=None,
            response_compression_algorithm=None,
        )

        logger.info(f"Ending POST request") 
        return results
    
def _upload(directory_path, connection_string, container_name):
    container_client = ContainerClient.from_connection_string(connection_string, container_name)
    logger.info(f"Uploading contents of {directory_path} to Azure Blob Storage...")

    # Get the parent directory of the directory_path
    base_path = os.path.dirname(directory_path)

    # Walk through directory
    for root, _, files in os.walk(directory_path):
        for file in files:
            file_path = os.path.join(root, file)
            # Calculate relative path including the parent directory
            relative_path = os.path.relpath(file_path, base_path)
            blob_client = container_client.get_blob_client(blob=relative_path.replace(os.sep, '/'))  # Replace OS-specific path separators
            with open(file_path, 'rb') as data:
                blob_client.upload_blob(data, overwrite=True)
                logger.info(f"{relative_path} uploaded to blob storage")

    logger.info("All files successfully uploaded to Azure Blob Storage.")

if __name__ == "__main__":
    tc = TritonClient()
    #tc.addToModels("/Users/codycf/Desktop/arvo/bridge/src/backend/models/distil_alert_v1.pt", "/Users/codycf/Desktop/arvo/bridge/src/backend/configs/config.pbtxt")
    model_name = "distil_alert_v1"
    input_ids_data = [[101, 1045, 2066, 2000, 13260, 6172, 2046, 2026, 10266, 2011, 4851, 9223, 3980, 102]]
    attention_mask_data = [[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]]

    results = tc.test_infer(model_name, input_ids_data, attention_mask_data)
    output = results.get_response()

    if output['outputs'][0]['data'] is not None:
        data = output['outputs'][0]['data']
        logger.info(f"The 'data is {data}") 
    else:
        logger.info(f"Error: there is no data") 