'use client';

import { useChat } from 'ai/react';
import Conversation from '../components/conversation';

export default function Chat() {
  const { messages, input, handleInputChange, handleSubmit } = useChat();
  return (
    <div className="flex flex-col w-full max-w-md py-24 mx-auto">
      <form onSubmit={handleSubmit} className="w-full">
        <input
          className="w-full p-2 border border-gray-300 rounded shadow-xl"
          value={input}
          placeholder="Ask Anything..."
          onChange={handleInputChange}
          style={{ position: 'sticky', top: 0, zIndex: 1000 }}
        />
      </form>

      <div className="flex flex-col gap-4 mt-4 overflow-y-auto">
        {messages.map(m => (
          <div key={m.id} className={`p-3 rounded-lg shadow ${m.role === 'user' ? 'white' : 'bg-gray-100'}`}>
            <strong>{m.role === 'user' ? 'User: ' : 'AI: '}</strong>{m.content}
          </div>
        ))}
      </div>

      <Conversation />
    </div>

    
    
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
  );
}