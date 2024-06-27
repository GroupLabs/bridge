'use client'
import { useRef, useState } from 'react';
import axios from 'axios';

export default function Home() {
  const fileInputRef = useRef(null);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [fileUrl, setFileUrl] = useState(null);
  const [quiz, setQuiz] = useState([]);

  const handleButtonClick = () => {
    fileInputRef.current.click();
  };

  const handleFileChange = async (event) => {
    const file = event.target.files[0];
    if (file) {
      setUploadedFile(file);
      const url = URL.createObjectURL(file);
      setFileUrl(url);

      const formData = new FormData();
      formData.append('file', file);

      const response = await axios.post('http://localhost:8000/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      console.log(response.data.quiz);

      setQuiz(response.data.quiz);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center p-24">
      {!fileUrl && (
        <div className='flex flex-col items-center'>
          <div className="font-bold">
            SMART
          </div>
          <br />
          <div>
            A demonstration of the capabilities of Bridge.
          </div>
          <br />
        </div>
      )}
      {!fileUrl && (
        <div className="z-10 max-w-5xl w-full items-center justify-between font-mono text-sm lg:flex">
          <button
            type="button"
            className="relative block w-full rounded-lg border-2 border-dashed border-gray-300 p-12 text-center hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            onClick={handleButtonClick}
          >
            <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 14v20c0 4.418 7.163 8 16 8 1.381 0 2.721-.087 4-.252M8 14c0 4.418 7.163 8 16 8s16-3.582 16-8M8 14c0-4.418 7.163-8 16-8s16 3.582 16 8m0 0v14m0-4c0 4.418-7.163 8-16 8S8 28.418 8 24m32 10v6m0 0v6m0-6h6m-6 0h-6" />
            </svg>
            <span className="mt-2 block text-sm font-semibold text-gray-900">Add a slide deck</span>
          </button>
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            onChange={handleFileChange}
            accept=".pdf"
          />
        </div>
      )}
      {fileUrl && (
        <div className="mt-4 flex flex-col items-center">
          <div className="flex justify-between">
            <iframe
              src={`${fileUrl}#page=1`}
              width="400"
              height="500"
              className="border"
            ></iframe>
            <span className="ml-2 text-sm font-semibold text-gray-900">{uploadedFile.name}</span>
          </div>
          {quiz.length > 0 && (
            <div className="mt-4 w-full">
              <h2 className="text-xl font-bold mb-4">Quiz</h2>
              {quiz.map((question, index) => (
                <div key={index} className="mb-4">
                  <p className="font-semibold">{question.question}</p>
                  <ul className="list-disc ml-6">
                    {question.answers.map((answer, idx) => (
                      <li key={idx}>{answer}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </main>
  );
}