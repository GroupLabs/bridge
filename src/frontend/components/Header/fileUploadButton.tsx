import React from 'react';

const FileUploadButton = ({ onFileChange }) => {
  const fileInputRef = React.createRef<HTMLInputElement>();

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (onFileChange) {
      onFileChange(event.target.files);
    }
  };

  return (
    <div className="flex items-center">
      <button
        type="button"
        onClick={handleButtonClick}
        className="px-4 py-2 bg-gray-800 text-white rounded"
      >
        Upload File
      </button>
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />
    </div>
  );
};

export default FileUploadButton;
