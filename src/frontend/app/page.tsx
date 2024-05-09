'use client';

import { useChat } from 'ai/react';
import Conversation from '../components/conversation';
import AIResponseWithPDF from '../components/PDFresponse';


export default function Chat() {
  const { messages, input, handleInputChange, handleSubmit } = useChat();
  const pdfUrl = "https://www.abta.org/wp-content/uploads/2018/03/about-brain-tumors-a-primer-1.pdf";  // Example PDF URL
  //extract the latest AI response from the message array
  const latestAIResponse = messages.filter(m => m.role === 'assistant').slice(-1)[0]?.content || "Waiting for AI response..."
  //const aiResponse = "Mistral refers to a strong, cold, northwesterly wind that blows from southern France into the Gulf of Lion in the northern Mediterranean.";

  
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
        {messages.map(m => (
          <div key={m.id} className={`p-3 rounded-lg shadow ${m.role === 'user' ? 'white' : 'bg-gray-100'}`}>
            <strong>{m.role === 'user' ? 'User: ' : 'AI: '}</strong>{m.content}
          </div>
        ))}
      </div>

      <Conversation /> {/* Optional, depending on its purpose */}

      <div>
        <AIResponseWithPDF pdfSrc={pdfUrl} aiResponse={latestAIResponse} />
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