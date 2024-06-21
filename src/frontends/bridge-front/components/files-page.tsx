'use client'

import { useState, useEffect, useMemo, ChangeEvent, JSX, SVGProps } from 'react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { getSortedFiles, uploadFile } from '@/lib/actions/file'

type File = {
  name: any
  size: any
  type: any
  createdDate: string
}

type SortOrder = 'asc' | 'desc'

export function FilesPage() {
  const [files, setFiles] = useState<File[]>([])
  const [sortField, setSortField] = useState<string>('created')

  const [isUploading, setIsUploading] = useState<boolean>(true)
  const [sortBy, setSortBy] = useState<keyof File>('name')
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc')

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const uploadedFile = event.target.files?.[0]
    if (uploadedFile) {
      try {
        setIsUploading(true)
        await uploadFile(uploadedFile)
        console.log('Here')
        console.log(uploadedFile)
        setTimeout(fetchFiles, 1000)
        setIsUploading(false)
      } catch (error) {
        console.error('Error uploading file:', error)
        setIsUploading(false)
      }
    }
  }

  // Extract the file fetching logic into its own function so it can be reused
  const fetchFiles = () => {
    getSortedFiles(sortField)
      .then(response => {
        // Check if response is an array before calling map
        if (Array.isArray(response) && response.length > 0) {
          const mappedFiles = response.map((file: any) => ({
            name: file._source.document_name,
            size: file._source.Size,
            type: file._source.Type.slice(1).toUpperCase(),
            createdDate: new Date(file._source.Created).toLocaleDateString(
              undefined,
              {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
              }
            )
          }))
          setFiles(mappedFiles)
          setIsUploading(false)
        } else {
          console.error('Unexpected response:', response)
          // Optionally set some error state here
          setIsUploading(false)
        }
      })
      .catch(error => {
        console.error('Error fetching files:', error)
        // Optionally set some error state here
        setIsUploading(false)
      })
  }

  // Call fetchFiles in the useEffect hook instead of duplicating the logic
  useEffect(() => {
    fetchFiles()
  }, [sortField])

  useEffect(() => {
    getSortedFiles(sortField)
      .then(response => {
        if (response && response.length > 0) {
          const mappedFiles = response.map((file: any) => ({
            name: file._source.document_name,
            size: file._source.Size,
            type: file._source.Type.slice(1).toUpperCase(),
            createdDate: new Date(file._source.Created).toLocaleDateString(
              undefined,
              {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
              }
            )
          }))
          setFiles(mappedFiles)
        }
      })
      .catch(error => {
        console.error('Error fetching files:', error)
        // Optionally set some error state here
      })
  }, [sortField])

  const handleSort = (key: keyof File) => {
    if (sortBy === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(key)
      setSortOrder('asc')
    }
  }

  const sortedFiles = useMemo(() => {
    return [...files].sort((a, b) => {
      if (a[sortBy] < b[sortBy]) return sortOrder === 'asc' ? -1 : 1
      if (a[sortBy] > b[sortBy]) return sortOrder === 'asc' ? 1 : -1
      return 0
    })
  }, [files, sortBy, sortOrder])

  return (
    <div
      // onDrop={handleDrop}
      // onDragOver={e => e.preventDefault()}
      className="p-6 md:p-8 lg:p-10"
    >
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <label
            htmlFor="file-upload"
            className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium rounded-md hover:bg-primary-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-focus"
          >
            <UploadIcon className="w-5 h-5 mr-2" />
            Upload File
          </label>
          <input
            id="file-upload"
            type="file"
            className="hidden"
            onChange={handleUpload}
          />
          <Button
            variant="outline"
            size="icon"
            className="text-muted-foreground hover:bg-muted"
            onClick={() => handleSort('name')}
          >
            <AArrowUpIcon
              className={`w-5 h-5 ${
                sortBy === 'name'
                  ? sortOrder === 'asc'
                    ? 'rotate-180'
                    : ''
                  : ''
              }`}
            />
            <span className="sr-only">Sort by name</span>
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="text-muted-foreground hover:bg-muted"
            onClick={() => handleSort('size')}
          >
            <DatabaseIcon
              className={`w-5 h-5 ${
                sortBy === 'size'
                  ? sortOrder === 'asc'
                    ? 'rotate-180'
                    : ''
                  : ''
              }`}
            />
            <span className="sr-only">Sort by size</span>
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="text-muted-foreground hover:bg-muted"
            onClick={() => handleSort('createdDate')}
          >
            <CalendarDaysIcon
              className={`w-5 h-5 ${
                sortBy === 'createdDate'
                  ? sortOrder === 'asc'
                    ? 'rotate-180'
                    : ''
                  : ''
              }`}
            />
            <span className="sr-only">Sort by created date</span>
          </Button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full table-auto border-collapse">
          <thead>
            <tr className="bg-muted">
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                File Name
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                Size
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                Type
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                Created
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedFiles.map((file, index) => (
              <TableRow key={index} file={file} />
            ))}
            {isUploading && (
              <tr>
                <td colSpan={4} className="px-4 py-3">
                  <div className="flex items-center space-x-4">
                    <Skeleton className="h-12 w-12 rounded-full" />
                    <div className="space-y-2">
                      <Skeleton className="h-4 w-[250px]" />
                      <Skeleton className="h-4 w-[200px]" />
                    </div>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function TableRow({ file }: { file: File }) {
  return (
    <tr className="border-b border-muted/40 hover:bg-muted/20">
      <td className="px-4 py-3 text-sm font-medium text-foreground">
        <a
          href={`http://0.0.0.0:8000/downloads/${
            file.name
          }.${file.type.toLowerCase()}`}
        >
          {file.name}
        </a>
      </td>
      <td className="px-4 py-3 text-sm text-muted-foreground">{file.size}</td>
      <td className="px-4 py-3 text-sm text-muted-foreground">{file.type}</td>
      <td className="px-4 py-3 text-sm text-muted-foreground">
        {file.createdDate}
      </td>
    </tr>
  )
}

function CalendarDaysIcon(
  props: JSX.IntrinsicAttributes & SVGProps<SVGSVGElement>
) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M8 2v4" />
      <path d="M16 2v4" />
      <rect width="18" height="18" x="3" y="4" rx="2" />
      <path d="M3 10h18" />
      <path d="M8 14h.01" />
      <path d="M12 14h.01" />
      <path d="M16 14h.01" />
      <path d="M8 18h.01" />
      <path d="M12 18h.01" />
      <path d="M16 18h.01" />
    </svg>
  )
}

function DatabaseIcon(
  props: JSX.IntrinsicAttributes & SVGProps<SVGSVGElement>
) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M3 5V19A9 3 0 0 0 21 19V5" />
      <path d="M3 12A9 3 0 0 0 21 12" />
    </svg>
  )
}

function UploadIcon(props: JSX.IntrinsicAttributes & SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" x2="12" y1="3" y2="15" />
    </svg>
  )
}

function AArrowUpIcon(
  props: JSX.IntrinsicAttributes & SVGProps<SVGSVGElement>
) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3.5 13h6" />
      <path d="m2 16 4.5-9 4.5 9" />
      <path d="M18 16V7" />
      <path d="m14 11 4-4 4 4" />
    </svg>
  )
}
