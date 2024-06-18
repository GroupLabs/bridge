'use client'

import { useState } from 'react'
import { CardContent, Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { SearchResult } from '@/lib/types'

export interface SearchResultsProps {
  results: SearchResult[]
}

export function SearchResults({ results = [] }: SearchResultsProps) {
  const [showAllResults, setShowAllResults] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [modalContent, setModalContent] = useState('')

  const handleViewMore = () => {
    setShowAllResults(true)
  }

  const openModal = (text: string) => {
    setModalContent(text)
    setIsModalOpen(true)
  }

  const closeModal = () => {
    setIsModalOpen(false)
  }

  const displayedResults = showAllResults ? results : results.slice(0, 3)
  const additionalResultsCount = results.length > 3 ? results.length - 3 : 0

  return (
    <div className="flex flex-wrap">
      {displayedResults.map((result, index) => (
        <div className="w-1/2 md:w-1/4 p-1" key={index}>
          <Card className="flex-1" onClick={() => openModal(result.text)}>
            <CardContent className="p-2">
              <p className="text-xs line-clamp-2">
                {result.text}
              </p>
              <div className="mt-2 flex items-center space-x-2">
                <div className="text-xs opacity-60 truncate">
                  {result.score}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      ))}
      {!showAllResults && additionalResultsCount > 0 && (
        <div className="w-1/2 md:w-1/4 p-1">
          <Card className="flex-1 flex h-full items-center justify-center">
            <CardContent className="p-2">
              <Button
                variant={'link'}
                className="text-muted-foreground"
                onClick={handleViewMore}
              >
                View {additionalResultsCount} more
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {isModalOpen && (
        <div className="relative z-10" aria-labelledby="modal-title" role="dialog" aria-modal="true">
          <div className="fixed inset-0 bg-black bg-opacity-80 transition-opacity"></div>
          <div className="fixed inset-0 z-10 w-screen overflow-y-auto">
            <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
              <div className="relative transform overflow-hidden rounded-lg bg-card px-4 pb-4 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-xl">
                <div>
                  <div className="mt-3 text-justify sm:mt-5">
                    <div className="flex justify-between">
                      <span className="inline-flex items-center rounded-md bg-green-500/10 px-2 py-1 text-xs font-medium text-green-400 ring-1 ring-inset ring-green-500/20">chunk_text</span>
                    </div>
                    <div className="my-5 sm:my-5">
                      <p className="text-sm">{modalContent}</p>
                    </div>
                  </div>
                </div>
                <div className="">
                  <button type="button" className="inline-flex w-full justify-center rounded-md bg-black/30 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-black/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600" onClick={closeModal}>Done</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}