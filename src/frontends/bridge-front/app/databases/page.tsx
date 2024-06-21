'use client'

import { ConnectorsPage } from '@/components/connectors-page'
import { Separator } from '@/components/ui/separator'
import postgresqlimg from '@/public/images/postgresql.png'
import azureimg from '@/public/images/azure.png'
import mongodbimg from '@/public/images/mongodb.svg'
import mysqlimg from '@/public/images/mysql.svg'

const Home = () => {
  return (
    <div className="max-w-5xl mx-auto px-8">
      <h1 className="text-center text-5xl mt-12">Databases</h1>
      <Separator />
      <ConnectorsPage items={connectors} />
    </div>
  )
}

export const connectors = [
  {
    title: 'PostgreSQL',
    img: postgresqlimg,
    active: false
  },
  {
    title: 'Azure',
    img: azureimg,
    active: true
  },
  {
    title: 'MongoDB',
    img: mongodbimg,
    active: false
  },
  {
    title: 'MySQL',
    img: mysqlimg,
    active: false
  }
]

export default Home
