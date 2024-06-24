import streamlit as st
import os
from PIL import Image
import pandas as pd
import shutil

from demoutils import save_uploaded_file, process_pdf_tatr, pdf_to_image_per_page

if 'dfs' not in st.session_state:
    st.session_state['dfs'] = []

temp_folder = 'temp'
temp_created_flag = False

def remove_temp(temp_folder=temp_folder):
    try:
        shutil.rmtree(temp_folder)
        print(f"Directory '{temp_folder}' has been deleted successfully.")
    except OSError as e:
        print(f"Error: {e.strerror}")

with st.sidebar:
    st.title("Data Ingestor")
    st.subheader("(Human in the Loop)")
    st.divider()
    data = st.file_uploader("Data", label_visibility='collapsed', type='pdf', on_change=remove_temp)

if data is not None:
    temp_file_path = save_uploaded_file(data)
    temp_created_flag = pdf_to_image_per_page(temp_file_path, 'temp')

def load_images_from_folder(folder):
    # Get all file names and sort them
    filenames = sorted([f for f in os.listdir(folder) if f.endswith((".png", ".jpg", ".jpeg"))])
    
    for filename in filenames:
        yield os.path.join(folder, filename)


if temp_created_flag:
    # Load images
    images = list(load_images_from_folder(temp_folder))

    # Create tabs for each image
    tab_titles = [f"Page {i+1}" for i in range(len(images))]
    tabs = st.tabs(tab_titles)

    for tab, image_path in zip(tabs, images):
        with tab:

            image_cont = st.empty()

            image = Image.open(image_path)

            image_cont.image(image, caption=os.path.basename(image_path))
            
            try:
                tbimage, tbdf, tbdata = process_pdf_tatr(image)

                st.session_state['dfs'].append(tbdf)

                with image_cont.container():
                    col1, col2 = st.columns(2)

                    st.data_editor(tbdf)

                    with col1:
                        st.image(image, caption=os.path.basename(image_path))

                    with col2:
                        st.image(tbimage)
            
            except IndexError:
                st.info("No table found")


@st.cache_resource
def convert_df(dfs):
    # IMPORTANT: Cache the conversion to prevent computation on every rerun

    df = pd.concat(dfs)

    return df.to_csv().encode('utf-8')

with st.sidebar:
    if len(st.session_state['dfs']) > 0:

        st.toast("Ready to download")

        st.download_button(
            label="Download data as CSV",
            data=convert_df(st.session_state['dfs']),
            file_name=f'{data.name}.csv',
            mime='text/csv',
        )
