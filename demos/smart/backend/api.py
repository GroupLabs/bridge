from dotenv import load_dotenv
import os
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pdfminer.high_level import extract_text
import io
import instructor
from pydantic import BaseModel
from typing import List
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# Set OpenAI API key
api_key = os.getenv('OPENAI_API_KEY')

# Patch the OpenAI client with instructor
client = instructor.from_openai(OpenAI(api_key=api_key))

app = FastAPI()

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this according to your frontend's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the response model for individual quiz questions
class QuizQuestion(BaseModel):
    question: str
    answers: List[str]

# Define the response model for the quiz with multiple questions
class Quiz(BaseModel):
    questions: List[QuizQuestion]

def truncate_text(text, max_words=5000):
    words = text.split()
    if len(words) > max_words:
        words = words[:max_words]
    return ' '.join(words)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Read file contents
    contents = await file.read()
    
    # Create an in-memory bytes buffer
    pdf_buffer = io.BytesIO(contents)
    
    # Extract text from the PDF file
    text = extract_text(pdf_buffer)
    
    # Truncate text to a maximum of 5000 words
    truncated_text = truncate_text(text)
    
    # Use OpenAI API to generate quiz questions in markdown format
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        response_model=Quiz,
        messages=[
            {"role": "system", "content": "You are a quiz generator."},
            {"role": "user", "content": f"Generate a quiz based on the following text in markdown format:\n\n{truncated_text}"}
        ],
        max_tokens=1500
    )

    # Extract the quiz from the response
    quiz = response
    
    return {"quiz": quiz.questions}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)