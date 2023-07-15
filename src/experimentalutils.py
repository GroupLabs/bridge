import openai

def generate_code(prompt, MODEL, ans_is_scalar, role="user", stream=False):

    code_prompt = f"You are a computer engineer that can only speak in code. Only return valid Python code. {prompt}. Express results in a matplotlib pyplot. Do not show the pyplot, instead save it as temp.png. Only return code. Store the answer in a variable named result."

    completion = openai.ChatCompletion.create(
    model=MODEL,
    messages=[
        {"role": role, "content": code_prompt}
    ],
    temperature=0,
    stream=stream
    )

    return completion["choices"][0]["message"]["content"]

def create_metadata(role="user", stream=False):

    code_prompt = f"Generate searchable metadata for the following CSV. Make it so that I can search for that metadata through a similarity search. Make the generated data include unique words about the CSV."

    n = " ID,Name,Age,Occupation,Department,Salary\
        1,Alice,30,Software Engineer,IT,75000\
        2,Bob,25,Graphic Designer,Marketing,55000\
        3,Charlie,22,Data Analyst,Finance,60000\
        4,David,28,Marketing Manager,Marketing,70000\
        5,Eve,24,Product Manager,Product,65000\
        6,Frank,32,HR Manager,Human Resources,72000\
        7,Grace,27,Accountant,Finance,58000\
        8,Hank,35,Project Manager,Product,80000\
        9,Ivy,29,Content Writer,Marketing,48000\
        10,Jane,31,Network Administrator,IT,67000"

    t = code_prompt + n + " only return a JSON and nothing else."


    completion = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "user", "content": "Hello"}
    ],
    temperature=0,
    stream=False
    )



    return completion