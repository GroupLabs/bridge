# https://github.com/triton-inference-server/client/tree/main/src/python/examples
# Installation issues: https://github.com/triton-inference-server/server/issues/3603
# Model repo: https://github.com/triton-inference-server/server/blob/main/docs/user_guide/model_repository.md#repository-layout

# TODO add config
import os
import tritonclient.http as httpclient
from tritonclient.utils import InferenceServerException # for custom error handling later
from log import setup_logger
import numpy as np
from config import config

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
        self.model_repository_path = config.MODEL_REPOSITORY_PATH # Default path if not specified in .env
        # if self.triton_client.is_server_ready():
        #     logger.info("Triton is available")
        # else:
        #     logger.info("Triton is not available")
        #     logger.info(config.TRITON_URL)

        logger.info(config.TRITON_URL)
        logger.info(config.TRITON_URL)
        logger.info(config.TRITON_URL)

    def addToModels(self, model_name, config):
        #model_name is path
        #config is path
        name, extension = os.path.splitext(os.path.basename(model_name))
        found = False
        existingModels = self.triton_client.get_model_repository_index()
        for model in existingModels:
            if model['name'] == name:
                logger.info(f"Model '{name}' already exists.")
                found = True
        if not found:
            logger.info(f"Adding model '{name}'.")

            if os.path.exists(model_name):
                if os.path.exists(config):
                    model_path = os.path.join(self.model_repository_path, name)
                    os.makedirs(model_path, exist_ok=True)
                    os.rename(config, model_path + "/" + os.path.basename(config))


                    model_version_path = os.path.join(model_path, "1")
                    os.makedirs(model_version_path, exist_ok=True)
                    newPath = model_version_path + "/" + os.path.basename(model_name)
                    os.rename(model_name, newPath)

                    os.rename(newPath ,  model_version_path + "/model" + extension)

                    logger.info(f"Successfully added model") 

                    
                else:
                    logger.info(f"Error: Config file does not exist at '{config}'") 
            else:
                logger.info(f"Error: Model file does not exist at '{model_name}'") 


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