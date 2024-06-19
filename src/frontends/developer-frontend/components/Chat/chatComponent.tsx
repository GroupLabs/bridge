import React, { useState } from 'react';

const ChatComponent = ({ chatId, messages, onSendMessage }) => {
  const [input, setInput] = useState('');

  const handleInputChange = (event) => {
    setInput(event.target.value);
  };

  const handleSendMessage = (event) => {
    event.preventDefault();
    onSendMessage(chatId, input);
    setInput(''); // Clear input after sending
  };

  return (
    <div className="flex flex-col flex-grow pt-16 px-4">
      {messages[chatId].map((m) => (
        <div key={m.id} className="whitespace-pre-wrap mt-2">
          {m.role === 'user' ? 'User: ' : 'AI: '}
          {m.content}
        </div>
      ))}
      <form onSubmit={handleSendMessage} className="mt-auto flex">
        <input
          type="text"
          value={input}
          onChange={handleInputChange}
          className="flex-grow p-2 border border-gray-300 rounded"
          placeholder="Type a message..."
        />
        <button type="submit" className="ml-2 p-2 bg-blue-500 text-white rounded">
          Send
        </button>
      </form>
    </div>
  );
};

export default ChatComponent;
