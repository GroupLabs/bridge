// components/UploadAndParse.js

import { useState } from 'react';
import axios from 'axios';

export default function UploadAndParse({ setParsedContent }) {
  const [file, setFile] = useState(null);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleUpload = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('/api/parse', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setParsedContent(response.data.documents[0].text); // Assuming the first document contains the parsed markdown
    } catch (error) {
      console.error('Error uploading file:', error);
    }
  };

  return (
    <div>
      <input type="file" onChange={handleFileChange} />
      <button onClick={handleUpload}>Upload and Parse</button>
    </div>
  );
}