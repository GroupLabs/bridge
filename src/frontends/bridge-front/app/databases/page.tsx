'use client'

import { DatabasesPage } from '@/components/databases-page'
import { Separator } from '@/components/ui/separator'
import useDatabasesWithData from './databasesData'
import { useState, useEffect } from 'react'

const Home = () => {
  const { databasesWithData: databases, isLoading } = useDatabasesWithData() // Destructure to get both values

  return (
    <div className="max-w-5xl mx-auto px-8">
      <h1 className="text-center text-5xl mt-12">Databases</h1>
      <Separator />
      <DatabasesPage items={databases} isLoading={isLoading} />
    </div>
  )
}

export default Home
