import React from 'react';
import FileUploadButton from './fileUploadButton'; // Adjust the import path as necessary

const Header = ({ input, handleInputChange, handleSubmit, onFileChange }) => {
  return (
    <header className="w-full bg-purple-800 shadow-md fixed top-0 left-0 z-10 flex items-center justify-between p-4">
      <div className="flex w-full max-w-3xl mx-auto items-center">
        <form onSubmit={handleSubmit} className="flex flex-grow relative mr-2">
          <input
            className="flex-grow p-2 border border-gray-300 rounded-l rounded-r-none"
            value={input}
            placeholder="How can I help you?"
            onChange={handleInputChange}
            type="text"
          />
          <button type="submit" className="absolute right-1 top-1 bottom-1 px-4 bg-gray-800 text-white">
            {"->"}
          </button>
        </form>
        <FileUploadButton onFileChange={onFileChange} />
      </div>
    </header>
  );
};

export default Header;
