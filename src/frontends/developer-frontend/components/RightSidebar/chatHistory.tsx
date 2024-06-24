import React from 'react';

const ChatHistorySidebar = ({ chats, onSelectChat, selectedChatId }) => {
  return (
    <aside className="w-1/5 h-[calc(100%-64px)] bg-gray-100 p-4 shadow-md fixed top-16 right-0">
      <h2 className="text-xl font-bold mb-4">Chat History</h2>
      <ul className="space-y-2">
        {chats.length > 0 ? (
          chats.map((chat) => (
            <li
              key={chat.id}
              className={`text-sm text-gray-700 cursor-pointer p-2 rounded ${
                selectedChatId === chat.id
                  ? 'bg-gray-300'
                  : 'hover:bg-gray-200'
              }`}
              onClick={() => onSelectChat(chat.id)}
            >
              Chat {chat.id}
            </li>
          ))
        ) : (
          <li className="text-sm text-gray-500">No chats available</li>
        )}
      </ul>
    </aside>
  );
};

export default ChatHistorySidebar;
