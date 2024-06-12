import streamlit as st

from demoutilssve import save_uploaded_file, split_pdf_into_pages, docvqa_pipeline



with st.sidebar:
    st.title("Data Ingestor (Human in the Loop)")
    st.header("Example questions:")
    st.code("What is the length used by BRIDGE (LOC 131363) - S00132?")
    st.code("What is the amount owing based on billing date Oct-30-2023?")

    st.divider()

    data = st.file_uploader("Data (PDF, JPEG)", label_visibility='visible')

if data is not None:
    temp_file_path = save_uploaded_file(data)
    split_pdf_into_pages(temp_file_path, 'temp')

    query = st.text_input("Question")

    if query:
        ans, page_image = docvqa_pipeline(query)

        col1, col2 = st.columns(2)

        with col1:
            st.write(ans[0]['answer'])

        with col2:
            st.image(page_image)