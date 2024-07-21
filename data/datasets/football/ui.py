import streamlit as st
import requests
import time

import os
from dotenv import load_dotenv

load_dotenv()

connection_established = False
url = f"{os.getenv('SERVER_URL')}"
health_endpoint = f"{url}/health-check"
query_endpoint = f"{url}/query"
query_debug_endpoint = f"{url}/query-debug"

DEBUG = False

# Streamlit UI
st.title("Bridge Demo")

with st.expander("Specs"):
    st.code(
        f'''
        VERSION : \'{str(os.getenv("VERSION"))}\'\n
        ENVIRONMENT : \'{str(os.getenv("ENV"))}\'\n
        DATA : \'football dataset\'\n
        '''
    )

query = st.text_input("Query")

if query:
    payload = {"query": query}
    
    response = requests.post(query_endpoint, json=payload)
        
    with st.status("Querying Bridge...", expanded=True) as status:

        start_time = time.time()
        
        st.write("Data discovery mechanism...")
        st.write("Dependency resolution...")
        st.write("Step planning...")
            
        status.update(label=f"Bridge finished in {time.time() - start_time}s", state="running", expanded=False)
    
        st.write("Executing steps...")
        
        try:
            if DEBUG:
                st.code(response.json()["output"])
            exec(response.json()["output"], globals(), locals())
        except Exception:
            status.update(label="Self-healing method A", state="running")
            st.write("Self-healing...")
            
            payload = {"query": query, "model": "gpt-4"} # fallback on gpt-4 on exec error
        
            response = requests.post(query_endpoint, json=payload)
            try:
                if DEBUG:
                    st.code(response.json()["output"])
                
                exec(response.json()["output"], globals(), locals())
            except Exception as e:
                st.error(e)

        if "OUTPUT" in locals():
            OUTPUT = locals()['OUTPUT']
        elif "output" in locals():
            OUTPUT = locals()['output']
        else:
            status.update(label="Self-healing method B", state="running")
            st.write("Self-healing...")
            payload = {"query": query, "model": "gpt-4"} # fallback on gpt-4 on missing output
        
            response = requests.post(query_endpoint, json=payload)
            try:
                if DEBUG:
                    st.code(response.json()["output"])
                
                exec(response.json()["output"], globals(), locals())
            except Exception as e:
                st.error(e)
            
            if "OUTPUT" in locals():
                OUTPUT = locals()['OUTPUT']
            else:
                OUTPUT = "No OUTPUT variable returned."
                
        if response.status_code == 200:
            st.success("Server has a healthy response!")
        else:
            st.error(f"Failed to get response from server. Status code: {response.status_code}")
            status.update(label=f"Status code: {response.status_code}", state="error", expanded=False)
                
        status.update(label=f"Bridge finished in {time.time() - start_time}s", state="complete", expanded=False)
        
    st.subheader(OUTPUT)