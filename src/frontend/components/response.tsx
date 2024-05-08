//Display responses in a structured format

import React from 'react';

interface ResponseProps {
  response: string;
  source?: string;
}

const Response: React.FC<ResponseProps> = ({ response, source }) => {
  return (
    <div className="bg-gray-800 text-white p-4 rounded-lg shadow-md">
      <p className="text-sm">{response}</p>
      {source && <span className="text-xs text-gray-400">{source}</span>}
    </div>
  );
};

export default Response;