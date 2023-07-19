import json
import xgboost as xgb
import numpy as np

import json
import numpy as np
import xgboost as xgb

class Model:
    def __init__(self, data, target, **kwargs):
        with open('sources.json', "r") as json_file:
            sources = json.load(json_file)

        self.target = target
        self.model_info = sources[data]['models'][target]
        self.model = None

    def input_mode():
        pass

    def load_model(self):
        pass

    def predict(self):
        pass


class XGBoostModel(Model):
    def input_mode(self, **kwargs):
        return xgb.DMatrix(np.array(list(kwargs.values())).reshape((1, -1)))

    def load_model(self):
        self.model = xgb.Booster()
        self.model.load_model('models/' + self.target.replace(" ", "_") + '_' + self.model_info['model_task'] + '.bin')

    def predict(self, input):

        # Some input validation needed here

        score = self.model.predict(input)
        classification = [1 if s > 0.5 else 0 for s in score]
        return classification, score


def classifier(data, target, **kwargs):
    try:
        with open('sources.json', "r") as json_file:
            sources = json.load(json_file)
        
        model_type = sources[data]['models'][target]['model_type']
        
        model = None
        if model_type == 'xgboost':
            model = XGBoostModel(data, target, **kwargs)
            model.load_model()

            input = model.input_mode(**kwargs)

            return model.predict(input)
            
        # Add other types of models here:
        # elif model_type == 'another_type':
        #    model = AnotherTypeModel(data, target, **kwargs)
        else:
            raise Exception(f"Unsupported model type: {model_type}")
        
        return None
    except Exception as e:
        print(f"Error during model classification: {str(e)}")


n= classifier('equipment_status.csv', 'Accident Occurred', Temperature=-12.69638070956033,h=-1.4166499928577423,w=0.0967347766707744,eid=1380787,es=1.073504406365598)
print(n)