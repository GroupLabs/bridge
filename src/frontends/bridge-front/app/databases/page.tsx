'use client'

import { ConnectorsPage } from '@/components/connectors-page'
import { Separator } from '@/components/ui/separator'
import databases from './databasesData'

const Home = () => {
  return (
    <div className="max-w-5xl mx-auto px-8">
      <h1 className="text-center text-5xl mt-12">Databases</h1>
      <Separator />
      <ConnectorsPage items={databases} />
    </div>
  )
}

export default Home
