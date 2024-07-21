import { createStreamableUI, createStreamableValue } from 'ai/rsc'
import { CoreMessage, ToolCallPart, ToolResultPart, streamText, tool } from 'ai'
import { Section } from '@/components/section'
import { BotMessage } from '@/components/message'
import { getTools } from './tools'
import { getModel } from '../utils'

// HACK to skip passing fileIds to the tool!
import { searchSchema } from '../schema/search'
import { Card } from '@/components/ui/card'
import { SearchSection } from '@/components/search-section'
import { BridgeSearchResults } from '@/lib/types'
// HACK to skip passing fileIds to the tool!

// HACK to skip passing fileIds to the tool!
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

async function bridgeQuery(query: string, fileIds?: string[]): Promise<any> {
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
      "index": "text_chunk",
      "doc_ids": fileIds
    })
  })

  if (!response.ok) {
    throw new Error(`Error: ${response.status}`)
  }

  const data = await response.json()
  return transformData(data)
}
// HACK to skip passing fileIds to the tool!

export async function researcher(
  uiStream: ReturnType<typeof createStreamableUI>,
  streamableText: ReturnType<typeof createStreamableValue<string>>,
  messages: CoreMessage[],
  useSpecificModel?: boolean,
  fileIds?: string[]
) {
  let fullResponse = ''
  let hasError = false
  const answerSection = (
    <Section title="Answer">
      <BotMessage content={streamableText.value} />
    </Section>
  )

  const currentDate = new Date().toLocaleString()
  let tools = getTools({ uiStream, fullResponse })
  
  // HACK to skip passing fileIds to the tool!
  if (fileIds && fileIds.length > 0) {
    tools = {
      "search": tool({
        description: 'Search for information uploaded to the organization through Bridge.',
        parameters: searchSchema,
        execute: async ({ query }: { query: string }) => {
      
          let hasError = false
          const streamResultsBridge = createStreamableValue<string>()
          uiStream.append(
            <SearchSection 
              resultBridge={streamResultsBridge.value} 
            />
          )
          let searchResult
          try {
            searchResult = await bridgeQuery(query, fileIds)
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
    }
  }
  // HACK to skip passing fileIds to the tool!

  const result = await streamText({
    model: getModel(),
    maxTokens: 2500,
    system: `As a professional search expert, you possess the ability to search for any information on Bridge (a portal to the organization's documents) or the web.
    For each user query, utilize the search results to their fullest potential to provide additional information and assistance in your response.
    Try to address the user's question with organization documents through Bridge. If it is not possible, use the search results to your advantage.
    Aim to directly address the user's question, augmenting your response with insights gleaned from the search results.
    Whenever quoting or referencing information from a specific URL, always cite the source URL explicitly.
    The retrieve tool can only be used with URLs provided by the user. URLs from search results cannot be used.
    Please match the language of the response to the user's language. Current date and time: ${currentDate}`,
    messages,
    tools
  }).catch(err => {
    hasError = true
    fullResponse = 'Error: ' + err.message
    streamableText.update(fullResponse)
  })

  if (!result) {
    return { result, fullResponse, hasError, toolResponses: [] }
  }

  uiStream.update(null)

  const toolCalls: ToolCallPart[] = []
  const toolResponses: ToolResultPart[] = []
  for await (const delta of result.fullStream) {
    switch (delta.type) {
      case 'text-delta':
        if (delta.textDelta) {
          if (fullResponse.length === 0 && delta.textDelta.length > 0) {
            uiStream.update(answerSection)
          }

          fullResponse += delta.textDelta
          streamableText.update(fullResponse)
        }
        break
      case 'tool-call':
        toolCalls.push(delta)
        break
      case 'tool-result':
        if (!useSpecificModel && toolResponses.length === 0 && delta.result) {
          uiStream.append(answerSection)
        }
        if (!delta.result) {
          hasError = true
        }
        toolResponses.push(delta)
        break
      case 'error':
        console.log('Error: ' + delta.error)
        hasError = true
        fullResponse += `\nError occurred while executing the tool`
        break
    }
  }
  messages.push({
    role: 'assistant',
    content: [{ type: 'text', text: fullResponse }, ...toolCalls]
  })

  if (toolResponses.length > 0) {
    messages.push({ role: 'tool', content: toolResponses })
  }

  return { result, fullResponse, hasError, toolResponses }
}