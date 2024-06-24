// components/QueryDocument.js

import { useState } from 'react';
import axios from 'axios';

export default function QueryDocument({ setQueryResponse }) {
  const [query, setQuery] = useState('');

  const handleQueryChange = (e) => {
    setQuery(e.target.value);
  };

  const handleQuery = async () => {
    try {
      const response = await axios.post('/api/query', { query });
      setQueryResponse(response.data.response);
    } catch (error) {
      console.error('Error querying document:', error);
    }
  };

  return (
    <div>
      <input
        type="text"
        value={query}
        onChange={handleQueryChange}
        placeholder="Enter your query"
      />
      <button onClick={handleQuery}>Query</button>
    </div>
  );
}