import pandas as pd
import streamlit as st

import pandas as pd
from prophet import Prophet

import json
import xgboost as xgb
import numpy as np

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
        self.model.load_model('src/models/' + self.target.replace(" ", "_") + '_' + self.model_info['model_task'] + '.bin')

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

## Model Preparation

# Load your dataset
df_accidents = pd.read_csv('oil_pipeline_accidents.csv')

# Convert 'Accident Date/Time' to datetime
df_accidents['Accident Date/Time'] = pd.to_datetime(df_accidents['Accident Date/Time'])

# Create a new dataframe with the number of accidents per day
daily_accidents = df_accidents.groupby(df_accidents['Accident Date/Time'].dt.date).size().reset_index()
daily_accidents.columns = ['ds', 'y']

# Initialize the Prophet model
model_daily_accidents = Prophet()

# Fit the model_daily_accidents to the data
model_daily_accidents.fit(daily_accidents)



def forecast_daily_accidents_model(days_into_future):
    # Generate future dates
    future_dates = model_daily_accidents.make_future_dataframe(periods=days_into_future)  # forecast for the next year

    # Predict the accidents
    forecast = model_daily_accidents.predict(future_dates)

    # Plot the forecast
    return model_daily_accidents.plot(forecast)

def forecast_daily_accidents_model_components(days_into_future):
    # Generate future dates
    future_dates = model_daily_accidents.make_future_dataframe(periods=days_into_future)  # forecast for the next year

    # Predict the accidents
    forecast = model_daily_accidents.predict(future_dates)

    # Plot the forecast
    return model_daily_accidents.plot_components(forecast)

def equipment_status_classifier(t,h,w,eid,es):
    return classifier('equipment_status.csv', 'Accident Occurred', Temperature=t,h=h,w=w,eid=eid,es=es)