'use client';

import React, { useState, useEffect } from 'react';
import { useChat } from 'ai/react';
import Conversation from '../components/conversation';
import AIResponseWithPDF from '../components/PDFresponse';

export default function Chat() {
  const { messages, input, handleInputChange, handleSubmit } = useChat();
  const [responsePairs, setResponsePairs] = useState([]);
  const [lastAssistantMessage, setLastAssistantMessage] = useState("Waiting for AI response...");

  useEffect(() => {
    const assistantMessages = messages.filter(m => m.role === 'assistant');
    const latestAIResponse = assistantMessages[assistantMessages.length - 1]?.content || "Waiting for AI response...";
    setLastAssistantMessage(latestAIResponse);
  }, [messages]);

  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if(lastMessage && lastMessage.role === 'user') {
      const pdfUrl = "https://www.abta.org/wp-content/uploads/2018/03/about-brain-tumors-a-primer-1.pdf";
      setResponsePairs(prev => [...prev, { question: lastMessage.content, response: lastAssistantMessage, pdfUrl }]);
    }
  }, [messages, lastAssistantMessage]);

  return (
    <div className="flex flex-col w-full max-w-4xl py-20 mx-auto">
      <form onSubmit={handleSubmit} className="flex w-full justify-center items-center">
        <input
          className="w-full max-w-xl p-2 border border-gray-300 rounded shadow-xl"
          value={input}
          placeholder="Ask Anything..."
          onChange={handleInputChange}
          style={{ position: 'sticky', top: 0, zIndex: 1000 }}
        />
      </form>

      <div className="flex flex-col gap-4 mt-4 overflow-y-auto">
        {messages.filter(m => m.role === 'user').map(m =>  ( 
          <div key={m.id} className="p-3 rounded-lg shadow bg-gray-100">
            <strong>User: </strong>{m.content}
          </div>
        ))}
      </div>

      <Conversation /> {/* Optional, depending on its purpose */}

      <div>
        {responsePairs.map(pair => (
          <AIResponseWithPDF key={pair.question} pdfSrc={pair.pdfUrl} aiResponse={pair.response} />
        ))}
      </div>
    </div>
  );
}




    // <div className="flex flex-col w-full max-w-md py-24 mx-auto stretch">
    //   {messages.map(m => (
    //     <div key={m.id} className="whitespace-pre-wrap">
    //       {m.role === 'user' ? 'User: ' : 'AI: '}
    //       {m.content}
    //     </div>
    //   ))}

    //   <form onSubmit={handleSubmit}>
    //     <input
    //       className="fixed bottom-0 w-full max-w-md p-2 mb-8 border border-gray-300 rounded shadow-xl"
    //       value={input}
    //       placeholder="Ask Anything..."
    //       onChange={handleInputChange}
    //     />
    //   </form>
    // </div>