//split-view for pdf 

import React from 'react';

interface AIResponseWithPDFProps {
  pdfSrc: string;  // URL to the PDF file
  aiResponse: string;
}

const AIResponseWithPDF: React.FC<AIResponseWithPDFProps> = ({ pdfSrc, aiResponse }) => {
  return (
    <div className="flex h-screen">
      <div className="w-2/3 overflow-auto mr-5"> 
      <iframe src={pdfSrc} style={{ width: '100%', height: '100%', border: 'none' }}></iframe>
      </div>
      <div className="w-1/3 flex flex-col justify-center items-center bg-gray-800 text-white p-4"> 
        <textarea
          className = "w-full h-3/4 bg-gray-700 text-white p-3 border-none rounded"
          readOnly
          value={aiResponse}
          aria-label="AI"
        ></textarea>
      </div>
    </div>
  );
};

export default AIResponseWithPDF;
