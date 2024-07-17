import { createStreamableUI } from 'ai/rsc';
import { retrieveTool } from './retrieve';
import { searchTool } from './bridge-search';
import { webSearchTool } from './web-search'; // Import the new tool

export interface ToolProps {
  uiStream: ReturnType<typeof createStreamableUI>;
  fullResponse: string;
}

export const getTools = ({ uiStream, fullResponse }: ToolProps) => {
  const tools: any = {
    search: searchTool({ uiStream, fullResponse }),
    retrieve: retrieveTool({ uiStream, fullResponse }),
    webSearch: webSearchTool({ uiStream, fullResponse }), // Register the new tool
  };

  return tools;
};