//Store and Manage responses

import React, { useState } from 'react';
import AIResponse from './response';

const Conversation: React.FC = () => {
  const [responses, setResponses] = useState<Array<{id: number, text: string, source?: string}>>([]);

  // Example function to simulate adding responses
  const addResponse = (text: string, source?: string) => {
    const newResponse = { id: responses.length + 1, text, source };
    setResponses([...responses, newResponse]);
  };

  return (
    <div className="flex flex-col space-y-4 p-4">
      {responses.map(response => (
        <AIResponse key={response.id} response={response.text} source={response.source} />
      ))}
    </div>
  );
};

export default Conversation;
