from ollama import gen

def describe_table(input):

    resp = gen(f"The following is a table. Look at the columns and infer what the table is about. Return just the description - as detailed as possible, but keep it straight to the point: {input}")


    return resp

if __name__ == "__main__":
    print(describe_table("Example Input"))