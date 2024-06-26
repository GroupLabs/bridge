'use client'

import { DatabasesPage } from '@/components/databases-page'
import { Separator } from '@/components/ui/separator'
import useDatabasesWithData from './databasesData'

const Home = () => {
  const databases = useDatabasesWithData() // Invoke the hook to get the items

  return (
    <div className="max-w-5xl mx-auto px-8">
      <h1 className="text-center text-5xl mt-12">Databases</h1>
      <Separator />
      <DatabasesPage items={databases} />
    </div>
  )
}

export default Home
