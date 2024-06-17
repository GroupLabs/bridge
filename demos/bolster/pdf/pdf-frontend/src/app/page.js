'use client'

import { useState } from 'react';
import dynamic from 'next/dynamic';

const UploadAndParse = dynamic(() => import('../components/UploadAndParse'), {
  ssr: false,
});
const QueryDocument = dynamic(() => import('../components/QueryDocument'), {
  ssr: false,
});

export default function Home() {
  const [parsedContent, setParsedContent] = useState('');
  const [queryResponse, setQueryResponse] = useState('');

  return (
    <div>
      <h1>Llama Parse Frontend</h1>
      <UploadAndParse setParsedContent={setParsedContent} />
      <div>
        <h2>Parsed Content</h2>
        <pre>{parsedContent}</pre>
      </div>
      <QueryDocument setQueryResponse={setQueryResponse} />
      <div>
        <h2>Query Response</h2>
        <pre>{queryResponse}</pre>
      </div>
    </div>
  );
}