import axios from 'axios'

const SLACK_AUTH_URL = 'http://localhost:8000/slack_auth'

export async function authenticateSlack(): Promise<string> {
  try {
    const response = await axios.get(SLACK_AUTH_URL)
    return response.data.authorization_url
  } catch (error) {
    console.error(error)
    return 'An error occurred while trying to connect to slack.'
  }
}
