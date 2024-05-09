# test_your_script_name.py
import unittest
from unittest.mock import patch, AsyncMock
from your_script_name import chat  # Adjust the import according to your project structure

class TestChatFunction(unittest.TestCase):
    @patch('httpx.AsyncClient.post')
    async def test_chat_function(self, mock_post):
        # Setup mock
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json = AsyncMock(return_value={'choices': [{'delta': {'content': 'Test response from GPT-4'}}]})
        mock_post.return_value.__aenter__.return_value = mock_response

        # Execute
        async for response in chat([{"role": "user", "content": "Hello GPT-4"}]):
            # Assert
            self.assertIn('Test response from GPT-4', response)

if __name__ == '__main__':
    unittest.main()
