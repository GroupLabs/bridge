import os
import json
import time
from flask import Flask, render_template
from threading import Thread
from pprint import pprint
import subprocess
import json

from demoHR.embed import embed_passage, embed_query, similarity

app = Flask(__name__)

search_query = ""
tsq = ""
profiles = []  # Global dictionary to store profile data

def encode_search_query(raw_query, linkedin=True):
    """Encodes a search query for use in a URL, with special handling for LinkedIn search syntax."""
    
    raw_query = '"' + raw_query + '"'

    if linkedin:
        # Adding the LinkedIn-specific query parts
        linkedin_part = ' -intitle:"profiles" -inurl:"dir/ " site:linkedin.com/in/ OR site:linkedin.com/pub/'
        raw_query += linkedin_part

    print(raw_query)
    
    # Manually encode specific characters to match the exact desired output
    encoded_query = raw_query.replace(' ', '%20') \
                             .replace('"', '%22') \

    return encoded_query

def scan_directory(path):
    processed_files = set()
    while True:
        current_files = set()
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                if filename.endswith('.json'):
                    file_path = os.path.join(dirpath, filename)
                    current_files.add(file_path)
                    if file_path not in processed_files:
                        process_file(file_path)
                        processed_files.add(file_path)
        time.sleep(5)  # Delay for 5 seconds before scanning again



# Initialize profiles as a global list
profiles = []
existing_urls = set()  # This set will track which URLs have already been processed

def process_file(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)

        profile_url = data.get('url')
        if profile_url and profile_url not in existing_urls:
            # Compute embeddings for title and description
            title_description = data.get('title', '') + ' ' + data.get('description', '')
            embedding = embed_passage(title_description)
            s_vector = embed_query(search_query)

            # Calculate the similarity score and append the profile data
            profile_data = {
                'url': profile_url,
                'title': data.get('title'),
                'description': data.get('description'),
                'score': similarity(embedding, s_vector)
            }
            profiles.append(profile_data)
            existing_urls.add(profile_url)
            
            print(len(profiles))
        
    except Exception as e:
        print(f"Error processing file {file_path}: {str(e)}")
        # If there's an error, delete the file
        try:
            os.remove(file_path)
            print(f"Deleted file {file_path} due to errors.")
        except Exception as e:
            print(f"Failed to delete file {file_path}: {str(e)}")

def compute_similarities():
    """
    Compute similarities between all profiles based on their experiences.
    """
    names = list(profiles.keys())
    num_profiles = len(names)
    similarities = [[0] * num_profiles for _ in range(num_profiles)]

    for i in range(num_profiles):
        for j in range(i + 1, num_profiles):
            exp_i = " ".join([exp['roleTitle'] for exp in profiles[names[i]]])
            exp_j = " ".join([exp['roleTitle'] for exp in profiles[names[j]]])
            vec_i = embed_passage(exp_i)
            vec_j = embed_passage(exp_j)
            similarities[i][j] = similarity(vec_i, vec_j)
            similarities[j][i] = similarities[i][j]

    return similarities

@app.route('/')
def show_profiles():
    """Serve a page with profiles details including title and embedding score."""
    profile_details = [{'title': profile.get('title'), 'score': profile.get('embedding')} for profile in profiles]
    return render_template('profiles.html', profiles=profile_details)

def start_node_script(arg):
    command = ["node", "test.js", arg]
    subprocess.Popen(command)

def start_scan_thread(path):
    """
    Start the directory scanner in a separate thread.
    """
    thread = Thread(target=scan_directory, args=(path,))
    thread.daemon = True
    thread.start()

if __name__ == '__main__':
    start_node_script(encode_search_query("software engineer"))
    directory_path = './storage/datasets/default/'
    start_scan_thread(directory_path)
    app.run(debug=True, port=5000)


