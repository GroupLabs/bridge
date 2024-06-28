'use client'

import { ConnectorsPage } from '@/components/connectors-page'
import { Separator } from '@/components/ui/separator'
import connectors from './connectorsData'

const Home = () => {
  return (
    <div className="max-w-5xl mx-auto px-8">
      <h1 className="text-center text-5xl mt-12">Connectors</h1>
      <Separator />
      <ConnectorsPage items={connectors} />
    </div>
  )
}

export default Home
