import { createStreamableValue } from 'ai/rsc'
import { searchSchema } from '@/lib/schema/search'
import { Card } from '@/components/ui/card'
import { SearchSection } from '@/components/search-section'
import { ToolProps } from '.'
import { BridgeSearchResults } from '@/lib/types'

export const searchTool = ({ uiStream, fullResponse }: ToolProps) => ({
  description: 'Search for information uploaded to the organization through Bridge.',
  parameters: searchSchema,
  execute: async ({
    query
  }: {
    query: string
  }) => {
    let hasError = false
    // Append the search section for Bridge results
    const streamResultsBridge = createStreamableValue<string>()
    uiStream.append(
      <SearchSection 
        resultBridge={streamResultsBridge.value} 
      />
    )
    let searchResult
    try {
      searchResult = await bridgeQuery(query)
    } catch (error) {
      console.error('Bridge API error:', error)
      hasError = true
    }

    if (hasError) {
      fullResponse += `\nAn error occurred while searching for "${query}.`
      uiStream.update(
        <Card className="p-4 mt-2 text-sm">
          {`An error occurred while searching for "${query}".`}
        </Card>
      )
      return searchResult
    }

    streamResultsBridge.done(JSON.stringify(searchResult))
    return searchResult
  }
})

const transformData = (respData: any): BridgeSearchResults => {
  if (!Array.isArray(respData.resp)) {
    console.error('Expected array but received:', respData)
    return { query: '', results: [] }
  }

  const results = respData.resp.map((item: { id: string; score: number; text: string }) => ({
    id: item.id,
    score: item.score,
    content: item.text
  }))

  return {
    query: respData.query || '',
    results
  }
}

async function bridgeQuery(query: string): Promise<any> {
  const url = process.env.BRIDGE_URL;

  if (!url) {
    throw new Error('BRIDGE_URL is not defined');
  }
  
  const response = await fetch(`${url}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      "query": query,
      "index": "text_chunk"
    })
  })

  if (!response.ok) {
    throw new Error(`Error: ${response.status}`)
  }

  const data = await response.json()
  return transformData(data)
}