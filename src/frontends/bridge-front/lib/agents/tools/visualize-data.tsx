'use client'

import { createStreamableValue } from 'ai/rsc';
import { searchSchema } from '@/lib/schema/search';
import { Card } from '@/components/ui/card';
import { VisualizeDataSection } from '@/components/visualize-data-section';
import { ToolProps } from '.';
import { SearchResult } from '@/lib/types';
import { useUser } from '@clerk/clerk-react';

export const visualizeDataTool = ({
  uiStream,
  fullResponse,
}: ToolProps) => ({
  description: 'Visualize data for information',
  parameters: searchSchema,
  execute: async ({
    query,
    max_results,
    search_depth
  }: {
    query: string
    max_results: number
    search_depth: 'basic' | 'advanced'
  }) => {
    const { user } = useUser();
    const userId = user ? user.id : '';

    console.log('userId:', userId); // Log userId

    let hasError = false;
    // Append the search section
    const streamResults = createStreamableValue<string>();
    uiStream.append(<VisualizeDataSection result={streamResults.value} />);

    // Tavily API requires a minimum of 5 characters in the query
    const filledQuery =
      query.length < 5 ? query + ' '.repeat(5 - query.length) : query;
    let searchResult;
    try {
      console.log('Attempting to call bridgeQuery');
      searchResult = await bridgeQuery(query, userId);
      console.log('bridgeQuery result:', searchResult);
    } catch (error) {
      console.error('Search API error:', error);
      hasError = true;
    }

    if (hasError) {
      fullResponse += `\nAn error occurred while searching for "${query}.`;
      uiStream.update(
        <Card className="p-4 mt-2 text-sm">
          {`An error occurred while searching for "${query}".`}
        </Card>
      );
      return searchResult;
    }

    streamResults.done(JSON.stringify(searchResult));

    return searchResult;
  }
});

const transformData = (
  respData: any
): { query: string; results: SearchResult[] } => {
  if (!Array.isArray(respData.resp)) {
    console.error('Expected array but received:', respData);
    return { query: '', results: [] };
  }

  const results = respData.resp.map(
    ([id, { score, text }]: [string, { score: number; text: string }]) => ({
      id,
      score,
      text
    })
  );

  return {
    query: respData.query || '', // Assuming the `query` is included in the top level of the API response
    results
  };
}

async function bridgeQuery(query: string, userId: string): Promise<any> {
  console.log('Sending request with userId:', userId); // Log before sending request
  const response = await fetch(`http://0.0.0.0:8000/query_all/${userId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      query: query,
      index: 'text_chunk'
    })
  });

  if (!response.ok) {
    throw new Error(`Error: ${response.status}`);
  }

  const data = await response.json();
  return transformData(data);
}

export default visualizeDataTool; // Exporting the function as default