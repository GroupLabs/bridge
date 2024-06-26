import { useEffect, useState } from 'react'
import { getDatabases, DatabaseConnectionDetails } from '@/lib/actions/database'

import postgresqlimg from '@/public/images/postgresql.png'
import azureimg from '@/public/images/azure.png'
import mongodbimg from '@/public/images/mongodb.svg'
import mysqlimg from '@/public/images/mysql.svg'

export interface Database {
  title: string
  db_type: string
  img: any
  active: boolean
  connectionDetails: DatabaseConnectionDetails | null
}

const useDatabasesWithData = () => {
  const [databasesWithData, setDatabasesWithData] = useState<Database[]>([])

  useEffect(() => {
    const fetchDatabases = async () => {
      const initialDatabases: Database[] = [
        {
          title: 'PostgreSQL',
          db_type: 'postgresql',
          img: postgresqlimg,
          active: false,
          connectionDetails: null
        },
        {
          title: 'Azure',
          db_type: 'azure',
          img: azureimg,
          active: false,
          connectionDetails: null
        },
        {
          title: 'MongoDB',
          db_type: 'mongodb',
          img: mongodbimg,
          active: false,
          connectionDetails: null
        },
        {
          title: 'MySQL',
          db_type: 'mysql',
          img: mysqlimg,
          active: false,
          connectionDetails: null
        }
      ]

      try {
        const databaseConnections = await getDatabases()
        const updatedDatabases = initialDatabases.map(db => {
          const connectionDetails =
            databaseConnections.find(conn => conn.db_type === db.db_type) ||
            null
          return { ...db, active: !!connectionDetails, connectionDetails }
        })
        setDatabasesWithData(updatedDatabases)
      } catch (error) {
        console.error('Failed to fetch databases:', error)
      }
    }

    fetchDatabases()
  }, [])

  return databasesWithData
}

export default useDatabasesWithData
