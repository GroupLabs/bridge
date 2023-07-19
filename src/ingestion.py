import json, os
import pandas as pd

from utils import PARAMS, init_apis, vec_db, llm, log_question_answer

params = PARAMS() # init parameters
index = init_apis() # initialize openai and pinecone connection

# Read sources from the text file

with open('sources.json', "r") as json_file:
    sources = json.load(json_file)

for source in sources:

    source_path = "metadata/" + source + ".json"

    if not os.path.exists(source_path):

        if source.endswith('.csv'):
            print(f"Creating metadata for {source}")

            csv_file = '../data/' + source 

            df = pd.read_csv(csv_file)
            header = df.columns.tolist()

            metadata = llm(prompt=params.prompts["metadata"].format(context=header), model=params.ADV_CHAT_MODEL)["content"]
            try:
                metadata = json.loads(metadata)
            except json.decoder.JSONDecodeError as e:
                try:
                    metadata = json.loads(f'{{{metadata}}}')
                except json.decoder.JSONDecodeError as e:
                    print("Error in metadata generation")
                    print(e)
                    print(metadata)

        res = {
            "source_name" : source,
            "type" : "csv" if source.endswith('.csv') else "unsupported format",
            "meta" : metadata,
        }

        json_str = json.dumps(res, indent=4)

        with open(source_path, "w") as json_file:
            json_file.write(json_str)

    # ingest into numpy vec db
    # numpy_db.ingest(res)

    # Predict target variables, and type of task [classification, anomaly detection, regression, etc.]
    # predictions, task_type = model.predict(res)

    # Auto-train model
    # model.auto_train(res, predictions)

    # Save model state and generate callable function (that can be accessed by decision making AI - OpenAI function calling in this case)
    # model.save_state()
    # callable_function = model.generate_callable_function()







# # Just psuedo code

# # sources = sources.txt # list of sources to ingest

# # for source in sources:
# #     create_metadata(source)

# #     if source is not csv:
# #         transform source to csv
    
# #     metadata = llm(prompt=params.prompts["metadata"].format(csv=context), MODEL=chat_model)["content"]

# #     res = {
# #         "source_name" : "source",
# #         "type" : "csv | database, tsv, xslx, etc.",
# #         "metadata": metadata,
# #     }

# #     # ingest into numpy vec db

# #     # Predict target variables, and type of task [classification, anomaly detection, regression, etc.]

# #     # Auto-train model

# #     # Save model state and generate callable function (that can be accessed by decision making AI - OpenAI function calling in this case)

# # Python version of the pseudocode
