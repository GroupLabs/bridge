'use client';

import React, { useState, useEffect } from 'react';
import { useChat } from 'ai/react';
import Header from '../../components/Header/header';
import Sidebar from '../../components/LeftSidebar/sidebar';
import ChatHistorySidebar from '../../components/RightSidebar/chatHistory';
import AIResponseWithPDF from '../../components/PDFresponse';

export default function Chat() {
  const { messages, input, handleInputChange, handleSubmit } = useChat();
  const [chatPairs, setChatPairs] = useState([]);
  const [uploadedFiles, setUploadedFiles] = useState({});
  const [chats, setChats] = useState([{ id: 1 }, { id: 2 }]); // Example chats
  const [selectedChat, setSelectedChat] = useState(1);
  const pdfURL = "https://www.abta.org/wp-content/uploads/2018/03/about-brain-tumors-a-primer-1.pdf" //placeholder pdf

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

  const handleFileChange = (files) => {
    if (files) {
      const newFiles = Array.from(files);
      setUploadedFiles((prevFiles) => ({
        ...prevFiles,
        [selectedChat]: [...(prevFiles[selectedChat] || []), ...newFiles],
      }));
      console.log('Selected files:', newFiles);
    }
  };

  const handleSelectChat = (chatId) => {
    setSelectedChat(chatId);
  };

  const handleSendMessage = (event) => {
    event.preventDefault();
    if (input.trim() === '') return;

    const newMessage = {
      id: Date.now(), // unique ID for the message
      role: 'user',
      content: input,
    };

  };

  return (
    <div className="flex w-full h-screen">
      <Header 
        input={input} 
        handleInputChange={handleInputChange} 
        handleSubmit={handleSubmit} 
        onFileChange={handleFileChange} 
      />
      <Sidebar files={uploadedFiles[selectedChat] || []} />
      <div className="flex flex-col flex-grow ml-[25%] mr-[25%] pt-16 px-4">
        <div className="flex flex-col gap-4 mt-4 overflow-y-auto">
          {chatPairs.map((pair, index) => (
            <div key={`pair-${index}`}>
              <div className="p-3 rounded-lg shadow bg-gray-100">
                <strong>User: </strong>{pair.user}
              </div>
              <AIResponseWithPDF pdfSrc={pdfURL} aiResponse={pair.assistant} />
              {/* Add a thin line between each pair */}
              {index !== chatPairs.length - 1 && <hr className="border-gray-300 my-4" />}
            </div>
          ))}
        </div>
      </div>
      <ChatHistorySidebar
        chats={chats}
        onSelectChat={handleSelectChat}
        selectedChatId={selectedChat}
      />
    </div>
  );
}
