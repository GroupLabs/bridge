import axios from 'axios'

const BASE_URL = 'http://localhost:8000/'


export async function authenticateConnector(connectorUrl: string): Promise<string> {
  try {
    const response = await axios.get(`${BASE_URL}${connectorUrl}`)
    return response.data.authorization_url
  } catch (error) {
    console.error(error)
    return 'An error occurred while trying to connect to slack.'
  }
}

export async function pingConnector(connectorUrl: string): Promise<boolean> {
  try {
    const response = await axios.get(`${BASE_URL}${connectorUrl}`)
    return response.data.is_connected
  } catch (error) {
    console.error(error)
    return false
  }
}