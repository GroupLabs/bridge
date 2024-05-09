'use client';

import React, { useState, useEffect } from 'react';
import { useChat } from 'ai/react';
import Conversation from '../../components/conversation';
import AIResponseWithPDF from '../../components/PDFresponse';

export default function Chat() {
  const { messages, input, handleInputChange, handleSubmit } = useChat();
  const [chatPairs, setChatPairs] = useState([]);

  useEffect(() => {
    let updatedChatPairs = [];
    let currentPair = { user: null, assistant: null };

    messages.forEach(msg => {
      if (msg.role === 'user') {
        // If there's an existing pair, push it to the updated pairs array
        if (currentPair.user !== null && currentPair.assistant !== null) {
          updatedChatPairs.push(currentPair);
          currentPair = { user: null, assistant: null };
        }
        // Assign user message to the current pair
        currentPair.user = msg.content;
      } else if (msg.role === 'assistant' && currentPair.user !== null) {
        // Assign assistant message to the current pair only if there's a corresponding user message
        currentPair.assistant = msg.content;
      }
    });

    // Push the last pair if it's incomplete
    if (currentPair.user !== null && currentPair.assistant !== null) {
      updatedChatPairs.push(currentPair);
    }

    // Reverse the order of chat pairs
    setChatPairs(updatedChatPairs.reverse());
  }, [messages]);

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
        {chatPairs.map((pair, index) => (
          <React.Fragment key={`pair-${index}`}>
            <div className="p-3 rounded-lg shadow bg-gray-100">
              <strong>User: </strong>{pair.user}
            </div>
            <AIResponseWithPDF pdfSrc="https://www.abta.org/wp-content/uploads/2018/03/about-brain-tumors-a-primer-1.pdf" aiResponse={pair.assistant} />
          </React.Fragment>
        ))}
      </div>

      <Conversation /> {/* Optional, depending on its purpose */}
    </div>
  );
}
