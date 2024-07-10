import streamlit as st
import requests
import json
import chromadb
from transformers import pipeline

from pdf_gen import *

from pdf_utils import pdf_to_image, handle_uploaded_file, Prompt

from dotenv import load_dotenv
import os

load_dotenv()

chroma_path = './chroma/'
client = chromadb.PersistentClient(path=chroma_path)

collection = client.get_or_create_collection("cratic-questions")

# if collection.count() == 0: # if collection is empty, add rows
#     for i, row in df.iterrows():              
#         collection.add(
#             documents=[row['question']],
#             metadatas={"topic" : row['topic'], "thread": row['thread']},
#             ids=str(row['_id']['$oid'])
#         )

print(f"Loaded {collection.count()} documents in vectorDB")

nlp = pipeline(
    "document-question-answering", 
    model="impira/layoutlm-invoices"
)

def decode_code(generated_code):
    try:
        split_text = generated_code.split("```")
        split_text = split_text[1] if len(split_text) > 1 else ""
        extracted_code = split_text.lstrip("`").rstrip("`").lstrip("python")

        # Encode and decode to utf-8
        sanitized_code = extracted_code.encode("utf-8", "ignore").decode("utf-8")

        return sanitized_code

    except Exception as e:
        print("An exception occurred:", e)
        return ""


if "thread" not in st.session_state:
    st.session_state.thread = [] # current thread

if "gen_thread" not in st.session_state:
    st.session_state.gen_thread = [] # current thread

if "llm_option" not in st.session_state:
    st.session_state.llm_option = None # current thread
    
if "img" not in st.session_state:
    st.session_state.img = None # current thread

with st.sidebar:
    st.header("Upload Files")
    uploaded_files = st.file_uploader("Choose any file", accept_multiple_files=False, label_visibility="collapsed", type="PDF")
    print(uploaded_files)
    if uploaded_files:
        path = handle_uploaded_file(uploaded_files, f"temp/{uploaded_files.name}")
        st.session_state.img = pdf_to_image(path)
    
        # st.toast(f"Loaded {len(uploaded_files)} / {collection.count()} document(s) to vectorDB")
        st.toast(f"Loaded {1} / {collection.count()} document(s) to vectorDB")
    
    del uploaded_files
    
    st.header("Options")
    
    mode = st.radio(
        "Choose mode:",
        ["Chat", "View PDF", "Generate"],
        captions=["Ask questions", "See the uploaded PDF", "Build a PDF"],
        index=None,
    )
    
    if mode == "Chat":
        st.session_state.llm_option = st.selectbox(
            "How would you like to be contacted?",
            ("impira/layoutlm-invoices", "GPT-4", "LLAMA2", "Mistral"),
            label_visibility="hidden",
            disabled=True
        )

if mode == "Chat":
    st.title(mode)
    
    def display_messages():
        for m in st.session_state.thread:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
                
    display_messages()


    if prompt := st.chat_input("Enter your response here"):
        
        st.session_state.thread.append({"role" : "user", "content" : prompt})
        
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):

            # data = {
            #     "query" : prompt,
            #     "thread" : [d["content"] for d in st.session_state.thread if d.get("role") == "user"],
            #     "complete_thread" : [d["content"] for d in st.session_state.thread if d.get("role")],
            #     "use_llm" : use_llm,
            #     "llm_threshold" : threshold_numerical,
            #     "llm_guidance" : guided_by_llm
            # }

            with st.spinner(''):
                
                ans = nlp(
                    st.session_state.img,
                    st.session_state.thread[-1]["content"]
                )
                
                # try:
                #     # Send a POST request to the API endpoint
                #     response = requests.post(inference_endpoint, headers=HEADERS, data=json.dumps(data)).json()
                # except Exception as e:
                #     st.write(e)
                    
                st.session_state.thread.append({"role" : "assistant", "content" : ans[0]['answer'], "confidence": ans[0]['score']})
                st.write(ans[0]['answer'])
                # st.markdown(f"confidence: {ans[0]['score']}")

if mode == "View PDF":
    st.title(mode)
    
    if st.session_state.img:
        st.image(st.session_state.img, use_column_width = "always", caption="Uploaded PDF (Processed)")
    else:
        st.write("No PDF uploaded.")
        
if mode == "Generate":
    
    inference_endpoint = 'https://api.openai.com/v1/chat/completions'
    
    HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {os.getenv("OPENAI_API_KEY")}'
    }
    
    pdf_template_obj = Prompt()
    
    if prompt := st.chat_input("Enter your response here"):
    
        st.session_state.gen_thread.append({"role" : "user", "content" : prompt})
    
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):

            data = {
                "model" : "gpt-4-1106-preview",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt + "\n\nUse the following as a template to updated:\n" + pdf_template_obj.pdf_template + "Only return code. My career depends on you returning full code. I am going to put your code in an exec(). Make sure it is only code. Do not comment out the execution part."
                    }
                ]
            }

            with st.spinner(''):
                
                try:
                    # Send a POST request to the API endpoint
                    response = requests.post(inference_endpoint, headers=HEADERS, data=json.dumps(data)).json()
                except Exception as e:
                    st.write(e)
                    
                code = decode_code(response['choices'][0]['message']['content'])
                    
                st.session_state.thread.append({"role" : "assistant", "content" : response['choices'][0]['message']['content']})
                st.code(code)
                
                pdf_template_obj.pdf_template = code
                
                exec(code)