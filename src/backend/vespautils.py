import requests
import os
from io import BytesIO
import zipfile

VESPA_CONFIG_URL = "http://localhost:19071/"
VESPA_PREPAREANDACTIVATE_ENDP = VESPA_CONFIG_URL + "application/v2/tenant/default/prepareandactivate"

def upload_config(search_config_path):
    if not os.path.isdir(search_config_path):
        raise ValueError(f"The path {search_config_path} does not exist or is not a directory")

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        for root, dirs, files in os.walk(search_config_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, search_config_path)
                zip_file.write(file_path, arcname)

    zip_buffer.seek(0)

    headers = {"Content-Type": "application/zip"}

    response = requests.post(VESPA_PREPAREANDACTIVATE_ENDP, headers=headers, data=zip_buffer)

    if response.status_code == 200:
        print("Deployment successful")
        print(response.text)
    else:
        # should retry, or graceful exit api.
        print("Deployment failed")
        print("Status code:", response.status_code)
        print("Response:", response.text)

if __name__ == "__main__":
    upload_config("./search-config")
