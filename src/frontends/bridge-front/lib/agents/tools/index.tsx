import { createStreamableUI } from 'ai/rsc'
import { retrieveTool } from './retrieve'
import { searchTool } from './search'
import { videoSearchTool } from './video-search'
import { visualizeDataTool } from './visualize-data'
import { CoreMessage } from 'ai'

export interface ToolProps {
  uiStream: ReturnType<typeof createStreamableUI>
  fullResponse: string
  messages?: CoreMessage[]
}

export const getTools = ({ uiStream, fullResponse, messages }: ToolProps) => {
  const tools: any = {
    search: searchTool({
      uiStream,
      fullResponse
    }),
    retrieve: retrieveTool({
      uiStream,
      fullResponse
    }),
    displayData: visualizeDataTool({
      uiStream,
      fullResponse,
      messages
    })
  }

  if (process.env.SERPER_API_KEY) {
    tools.videoSearch = videoSearchTool({
      uiStream,
      fullResponse
    })
  }

  // Check if we're running in a browser environment before adding fileSearch
  if (typeof window !== 'undefined') {
    const { fileSearchTool } = require('./file-search')
    tools.fileSearch = fileSearchTool({
      uiStream,
      fullResponse
    })
  }

  return tools
}