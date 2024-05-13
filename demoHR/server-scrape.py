import os
import json
import time
from flask import Flask, render_template, request, jsonify
from flask import redirect, url_for
from threading import Thread
import subprocess

from embed import embed_passage, embed_query, similarity

app = Flask(__name__)

profiles = []
existing_urls = set()

def encode_search_query(raw_query):
    """Encodes a search query for use in a URL, with special handling."""
    encoded_query = f'"{raw_query}" -intitle:"profiles" -inurl:"dir/ " site:linkedin.com/in/ OR site:linkedin.com/pub/'
    return encoded_query.replace(' ', '%20').replace('"', '%22')

def process_file(file_path, search_query):
    print("Processing file")
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        
        print(data)
        
        profile_url = data.get('url')
        if profile_url and profile_url not in existing_urls:
            title_description = data.get('title', '') + ' ' + data.get('description', '')
            embedding = embed_passage(title_description)
            s_vector = embed_query(search_query)
            profiles.append({
                'url': profile_url,
                'title': data.get('title'),
                'description': data.get('description'),
                'score': similarity(embedding, s_vector)
            })
            existing_urls.add(profile_url)

            profiles.sort(key=lambda x: x['score'], reverse=True)
    except Exception as e:

        print(f"Error: {e}")

def scan_directory(path, search_query):
    time.sleep(1)
    processed_files = set()
    while True:
        for dirpath, _, filenames in os.walk(path):
            for filename in filenames:
                if filename.endswith('.json'):
                    file_path = os.path.join(dirpath, filename)
                    if file_path not in processed_files:
                        process_file(file_path, search_query)
                        processed_files.add(file_path)
        time.sleep(5)

@app.route('/')
def show_profiles():
    return render_template('profiles.html', profiles=profiles)


@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        query = request.form.get('query', '')
    else:
        query = request.args.get('query', '')

    if query:
        encoded_query = encode_search_query(query)
        # start_scan_thread now updates global profiles directly
        profiles.clear()  # Clear existing profiles for a fresh search
        existing_urls.clear()
        # start node script
        start_node_script(encode_search_query(query))
        start_scan_thread(os.getenv('DIRECTORY_PATH', './storage/datasets/default'), encoded_query)
        return redirect(url_for('show_results'))
    else:
        return render_template('search.html', error='No search query provided')

@app.route('/results')
def show_results():
    print(profiles)
    return render_template('results.html', profiles=profiles)

@app.route('/get-profiles')
def get_profiles():
    return jsonify(profiles)


def start_node_script(arg):
    subprocess.Popen(["node", "test.js", arg])

def start_scan_thread(path, search_query):
    thread = Thread(target=scan_directory, args=(path, search_query))
    thread.daemon = True
    thread.start()

if __name__ == '__main__':
    app.run(debug=True, port=int(os.getenv('PORT', 5000)))

