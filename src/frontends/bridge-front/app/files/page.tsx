'use client'

import { Separator } from '@/components/ui/separator'
import { FilesPage } from '@/components/files-page'

const Home = () => {
  return (
    <div className="max-w-5xl mx-auto px-8">
      <h1 className="text-center text-5xl mt-12">Files</h1>
      <Separator />
      <FilesPage />
    </div>
  )
}

export default Home
