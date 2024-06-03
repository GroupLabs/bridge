from googleapiclient.discovery import build

def google_search(search_term, api_key, cse_id, **kwargs):
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=search_term, cx=cse_id, **kwargs).execute()
    return res['items']

api_key = "AIzaSyAuqxC5jcxQAb5R8CNbbJMpOZoLvKnSYgQ"  # Replace this with your actual API key
cse_id = "YOUR_CSE_ID"  # Replace this with your actual CSE ID

results = google_search("Python Programming", api_key, cse_id)
for result in results:
    print(result['title'])
    print(result['link'])
    print(result['snippet'])
    print("\n")
