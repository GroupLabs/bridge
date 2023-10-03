import streamlit as st
import requests
import time

import os
from dotenv import load_dotenv

load_dotenv()

connection_established = False
url = f"{os.getenv('SERVER_URL')}"
health_url = f"{url}/health-check"

# Streamlit UI
st.title("Bridge Demo")

with st.expander("Specs"):
    st.code(
        f'''
        VERSION : \'{str(os.getenv("VERSION"))}\'\n
        ENVIRONMENT : \'{str(os.getenv("ENV"))}\'\n
        '''
    )

tabs = []

    
query = st.text_input("Query")

# if explainable

    # vector store

    # if graph_ready
    # tabs.append("graph")




st.button("Reset")