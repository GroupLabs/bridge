'use client'

import { useState } from 'react'
import { CardContent, Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { SearchResult } from '@/lib/types'
import { LinkPreview } from '@/components/ui/link-preview'
import { File } from 'lucide-react'
import Image from 'next/image'
import githubimg from '@/public/images/github.svg'
import slackimg from '@/public/images/slack.svg'
import office365img from '@/public/images/office365.png'
import googledriveimg from '@/public/images/googledrive.svg'
import sapimg from '@/public/images/sap.svg'
import workdayimg from '@/public/images/workday.svg'
import salesforceimg from '@/public/images/salesforce.svg'

export interface SearchResultsProps {
  results: SearchResult[]
}

export function FileSearchResults({ results = [] }: SearchResultsProps) {
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
      {displayedResults.map((result, index) => {
        // Separate the file name from the rest of the text at the first ": "
        const separatorIndex = result.text.indexOf(': ')
        const fileName = result.text.substring(0, separatorIndex)
        const contentWithoutFileName = result.text.substring(separatorIndex + 2)

        return (
          <div className="w-1/2 md:w-1/4 p-1" key={index}>
            <Card
              className="flex-1"
              onClick={() => openModal(contentWithoutFileName)}
            >
              <CardContent className="p-2">
                <div className="flex gap-2">
                  {result.source === 'slack' ? (
                    <Image src={slackimg} alt="slackimg" className="h-6 w-6" />
                  ) : result.source === 'github' ? (
                    <Image
                      src={githubimg}
                      alt="githubimg"
                      className="h-6 w-6"
                    />
                  ) : result.source === 'google' ? (
                    <Image
                      src={googledriveimg}
                      alt="googledriveimg"
                      className="h-6 w-6"
                    />
                  ) : result.source === 'office365' ? (
                    <Image
                      src={office365img}
                      alt="office365img"
                      className="h-6 w-6"
                    />
                  ) : result.source === 'sap' ? (
                    <Image src={sapimg} alt="sapimg" className="h-6 w-6" />
                  ) : result.source === 'workday' ? (
                    <Image
                      src={workdayimg}
                      alt="workdayimg"
                      className="h-6 w-6"
                    />
                  ) : result.source === 'salesforce' ? (
                    <Image
                      src={salesforceimg}
                      alt="salesforceimg"
                      className="h-6 w-6"
                    />
                  ) : (
                    <File className="w-6 h-6" />
                  )}
                </div>
                <LinkPreview
                  url={`http://0.0.0.0:8000/downloads/${fileName}`}
                  imageSrc={`http://0.0.0.0:8000/downloads/preview/${fileName}`}
                  className="line-clamp-2 font-bold bg-clip-text text-transparent bg-gradient-to-br from-purple-500 to-pink-500"
                >
                  {fileName}
                </LinkPreview>

                <p className="text-xs line-clamp-2">{contentWithoutFileName}</p>
                <div className="mt-2 flex items-center space-x-2">
                  <div className="text-xs opacity-60 truncate">
                    {result.score}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )
      })}
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
        <div
          className="relative z-10"
          aria-labelledby="modal-title"
          role="dialog"
          aria-modal="true"
        >
          <div className="fixed inset-0 bg-black bg-opacity-80 transition-opacity"></div>
          <div className="fixed inset-0 z-10 w-screen overflow-y-auto">
            <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
              <div className="relative transform overflow-hidden rounded-lg bg-card px-4 pb-4 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-xl">
                <div>
                  <div className="mt-3 text-justify sm:mt-5">
                    <div className="flex justify-between">
                      <span className="inline-flex items-center rounded-md bg-green-500/10 px-2 py-1 text-xs font-medium text-green-400 ring-1 ring-inset ring-green-500/20">
                        text chunk
                      </span>
                    </div>
                    <div className="my-5 sm:my-5">
                      <p className="text-sm">{modalContent}</p>
                    </div>
                  </div>
                </div>
                <div className="">
                  <button
                    type="button"
                    className="inline-flex w-full justify-center rounded-md bg-black/30 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-black/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
                    onClick={closeModal}
                  >
                    Done
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
