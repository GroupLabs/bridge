import axios from 'axios'

const PING_DATABASE_URL = 'http://localhost:8000/ping_database'
const DATABASES_URL = 'http://localhost:8000/databases/'

export interface DatabaseConnectionDetails {
  db_type: string
  host?: string
  user?: string
  password?: string
  connection_id?: string
  connection_string?: string
}

export async function pingDatabase(
  connectionData: DatabaseConnectionDetails
): Promise<string> {
  const changedKeys = {
    database: connectionData.db_type,
    connectionString: connectionData.connection_string
  }
  try {
    const response = await axios.post(PING_DATABASE_URL, changedKeys)
    if (response.data.client === 'ok') {
      console.log('Database connection is successful.')
      return 'Database connection is successful.'
    } else {
      console.error('Failed to connect to the database.')
      return 'Failed to connect to the database.'
    }
  } catch (error) {
    console.error(error)
    return 'An error occurred while trying to connect to the database.'
  }
}

export async function getDatabases(): Promise<DatabaseConnectionDetails[]> {
  try {
    const response = await axios.get(DATABASES_URL)
    console.log('Retrieved database connections successfully.')
    return response.data
  } catch (error) {
    console.error(error)
    throw new Error(
      'An error occurred while trying to retrieve the database connections.'
    )
  }
}
