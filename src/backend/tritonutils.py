# https://github.com/triton-inference-server/client/tree/main/src/python/examples
# Installation issues: https://github.com/triton-inference-server/server/issues/3603
# Model repo: https://github.com/triton-inference-server/server/blob/main/docs/user_guide/model_repository.md#repository-layout

# TODO add config
import os
import tritonclient.http as httpclient
from tritonclient.utils import InferenceServerException # for custom error handling later
from dotenv import load_dotenv
from log import setup_logger

dotenv_path = os.path.join(os.path.dirname(__file__), '..', 'deployment', '.env')
load_dotenv(dotenv_path=dotenv_path)

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
            url="localhost:9000", 
            verbose=1
            ):
        self.triton_client = httpclient.InferenceServerClient(
            url=url, verbose=verbose
        )
        self.model_repository_path = os.getenv('MODEL_REPOSITORY_PATH') # Default path if not specified in .env
        logger.info("Triton is available")

    def addToModels(self, model_name, config):
        found = False
        existingModels = self.triton_client.get_model_repository_index()
        for model in existingModels:
            if model['name'] == model_name:
                self.triton_client.load_model(model_name, config) #assuming want to update model
                logger.info(f"Model {model_name} already exists.")
                found = True
        if not found:
            logger.info(f"Adding model {model_name}.")
            model_path = os.path.join(self.model_repository_path, model_name, '1')
            os.makedirs(model_path, exist_ok=True)
            logger.info(f"Model directory created at {model_path}")
            


        
        

if __name__ == "__main__":
    tc = TritonClient()
    tc.addToModels("test33", "sd")
    
