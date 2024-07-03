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
        // {
        //   title: 'PostgreSQL',
        //   db_type: 'postgresql',
        //   img: postgresqlimg,
        //   active: false,
        //   connectionDetails: null
        // },
        // {
        //   title: 'Azure',
        //   db_type: 'azure',
        //   img: azureimg,
        //   active: false,
        //   connectionDetails: null
        // },
        // {
        //   title: 'MongoDB',
        //   db_type: 'mongodb',
        //   img: mongodbimg,
        //   active: false,
        //   connectionDetails: null
        // },
        // {
        //   title: 'MySQL',
        //   db_type: 'mysql',
        //   img: mysqlimg,
        //   active: false,
        //   connectionDetails: null
        // }
      ]

      try {
        const databaseConnections = await getDatabases()
        const combinedDatabases = [
          ...initialDatabases,
          ...databaseConnections.map(db => ({
            img: getImageForDbType(db.db_type),
            db_type: db.db_type,
            title: getTitleForDbType(db.db_type),
            active: true,
            connectionDetails: db
          }))
        ]
        setDatabasesWithData(combinedDatabases)
      } catch (error) {
        console.error('Failed to fetch databases:', error)
      }
    }

    fetchDatabases()
  }, [])

  return databasesWithData
}

function getImageForDbType(db_type: string) {
  switch (db_type) {
    case 'postgresql':
      return postgresqlimg
    case 'azure':
      return azureimg
    case 'mongodb':
      return mongodbimg
    case 'mysql':
      return mysqlimg
    default:
      return null // Or a default image
  }
}

function getTitleForDbType(dbType: string): string {
  switch (dbType) {
    case 'mysql':
      return 'MySQL'
    case 'postgresql':
      return 'PostgreSQL'
    case 'mongodb':
      return 'MongoDB'
    case 'azure':
      return 'Azure'
    default:
      return 'Unknown Database'
  }
}

export default useDatabasesWithData
