import json
import xgboost as xgb
import numpy as np

def classifier(data, target, **kwargs):
    with open('sources.json', "r") as json_file:
        sources = json.load(json_file)

    if sources[data]['models'][target]['model_type'] == 'xgboost':
        
        loaded_model = xgb.Booster()
        loaded_model.load_model('models/' + target.replace(" ", "_") + '_' + sources[data]['models'][target]['model_task'] + '.bin')

        # Create an array
        array = np.array(list(kwargs.values()))

        # Reshape the array
        array = array.reshape((1, -1))

        # Convert the reshaped array to a DMatrix
        dmatrix = xgb.DMatrix(array)

        # Get the prediction score
        score = loaded_model.predict(dmatrix)

        print(score)

        # Apply a threshold to get the classification
        classification = [1 if s > 0.5 else 0 for s in score]

        return classification

n= classifier('equipment_status.csv', 'Accident Occurred', Temperature=-12.69638070956033,h=-1.4166499928577423,w=0.0967347766707744,eid=1380787,es=1.073504406365598)
print(n)