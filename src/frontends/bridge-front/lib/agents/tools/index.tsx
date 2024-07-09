import { createStreamableUI } from 'ai/rsc'
import { retrieveTool } from './retrieve'
import { searchTool } from './search'
import { videoSearchTool } from './video-search'
import { fileSearchTool } from './file-search'
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
    fileSearch: fileSearchTool({
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

  return tools
}
