


#def describe_table(input):
#
#    resp = "There is no LLM pluged in. Check auto-description"

#    return resp


def describe_picture(input):
    #  base64_image = encode_image(image_path)
    #  name = os.path.basename(image_path)


    #  headers = {
    #      'Content-Type': 'application/json',
    #      'Authorization': f'Bearer {OPENAI_KEY}'
    #  }
    #  data = {
    #      "model": LLM_MODEL,
    #      "messages": [
    #          {
    #              "role": "user",
    #              "content": [
    #                  {
    #                      "type": "text",
    #                      "text": f"The following is a picture, Describe what is in the picture - as detailed as possible, but keep it straight to the point, summarize in 30 words, include the file name. Keep in mind the file name as it might help in your description {name}: "
    #                  },
    #                  {
    #                      "type": "image_url",
    #                      "image_url": {
    #                          "url": f"data:image/jpeg;base64,{base64_image}"
    #                      }
    #                  }
    #              ]
    #          }
    #      ]
    #  }

    #  timeout = httpx.Timeout(300.0, read=300.0)

    #  with httpx.Client(timeout=timeout) as client:
    #      response = client.post(LLM_URL + "/chat/completions", headers=headers, json=data)
    #      if response.status_code == 200:
    #          return response.json()['choices'][0]['message']['content']  # Adjusted path for chat API responses
    #      else:
    #          raise Exception("Failed to generate text: " + response.text)

from ollama import gen2, chat_with_model_to_get_description

def describe_table(input):
    resp = gen2(f"The following is a table. Look at the columns and infer what the table is about. Return just the description - as detailed as possible, but keep it straight to the point: {input}")

    return resp

def describe_picture(input):
    resp = chat_with_model_to_get_description(input)
    return resp

if __name__ == "__main__":
    print(describe_table("Example Input"))