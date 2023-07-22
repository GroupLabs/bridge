import streamlit as st
from src.utils import PARAMS, init_apis, vec_db, llm, log_question_answer

st.title('Bridge Capabilities Demonstration')

params = PARAMS() # init parameters
index = init_apis() # initialize openai and pinecone connections

data_type = st.selectbox(
    'Demonstrate capabilities for:',
    ('Docs', 'Data Tables', 'Models'))

with st.sidebar:
    st.header('Examples')
    st.divider()
    st.write('Here are some examples of questions you can ask the Bridge API.')

    if data_type == 'Docs':
        st.write('What is the average cost of a well in the Montney?')
        st.write('What were segmented earnings in 2022 and 2023?')
        st.write('What was the comparable EBITDA in the first quarter of 2023?')

    if data_type == 'Data Tables':
        pass
    
    if data_type == 'Models':
        st.write('What is the accident probability if equipment status is "average" ?')

st.write('This is a demonstration of the capabilities of the Bridge API. The Bridge API is a RESTful API that allows you to access data from the Bridge data engine.')

user_input = st.text_input("Enter message")

if user_input:
    if data_type == 'Docs':
        # find context
        context = vec_db(query=user_input, index=index, embedding_model=params.EMBEDDING_MODEL, ns='tc-demo')

        # build prompt
        prompt = params.prompts["contextual-answer"].format(context=context, query=user_input)

        # llm to generate answer
        contextual_answer = llm(prompt=prompt, model=params.ADV_CHAT_MODEL)["content"]

        st.write(contextual_answer)