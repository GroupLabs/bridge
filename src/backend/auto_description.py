from ollama import gen1, chat_with_model_to_get_description

def describe_table(input):

    resp = gen1(f"The following is a table. Look at the columns and infer what the table is about. Return just the description - as detailed as possible, but keep it straight to the point, include the title of the file. keep in mind the title as it might help in your description: {input}")

    return resp

def describe_picture(input):
    resp = chat_with_model_to_get_description(input)
    return resp

if __name__ == "__main__":
    print(describe_table("Example Input"))