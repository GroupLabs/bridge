import { createStreamableUI } from 'ai/rsc';
import { retrieveTool } from './retrieve';
import { searchTool } from './search';
import { videoSearchTool } from './video-search';
import visualizeDataTool from './visualize-data'; // Importing the client-side function

export interface ToolProps {
  uiStream: ReturnType<typeof createStreamableUI>
  fullResponse: string
  messages?: CoreMessage[]
}

export const getTools = async ({ uiStream, fullResponse, messages }: ToolProps) => {
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
  };

  if (process.env.SERPER_API_KEY) {
    tools.videoSearch = videoSearchTool({
      uiStream,
      fullResponse
    });
  }

  // Check if we're running in a browser environment before adding client-only tools
  if (typeof window !== 'undefined') {
    // Import client-only tools dynamically
    const { fileSearchTool } = await import('./file-search');
    tools.fileSearch = fileSearchTool({
      uiStream,
      fullResponse
    });
  }

  return tools;
};