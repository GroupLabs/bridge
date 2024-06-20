'use client'

import React from 'react'
import { useState } from 'react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { MenubarShortcut } from '@/components/ui/menubar'
import { JSX, SVGProps } from 'react'

export interface ChatsProps {
  className?: string
}

export function Chats({ className }: ChatsProps) {
  const [topics, setTopics] = useState([
    { id: 1, title: "What's our marketing strategy?" },
    { id: 2, title: 'How can we improve our financial performance?' },
    { id: 3, title: 'What are the latest HR updates?' },
    { id: 4, title: 'How can we optimize our operations?' },
    { id: 5, title: "What's our business strategy for the next quarter?" },
    { id: 6, title: 'What are the current market trends?' },
    { id: 7, title: 'How can we enhance customer satisfaction?' },
    { id: 8, title: 'What are our technology upgrade plans?' },
    { id: 9, title: 'How can we increase employee engagement?' },
    { id: 10, title: "What's our sustainability strategy?" },
    { id: 11, title: 'How can we expand our product line?' },
    { id: 12, title: 'What are our key performance indicators?' },
    { id: 13, title: 'How can we improve our supply chain?' },
    { id: 14, title: "What's our plan for international expansion?" },
    { id: 15, title: 'How can we strengthen our brand identity?' }
  ])

  const [searchTerm, setSearchTerm] = useState('')
  const filteredTopics = topics.filter(topic =>
    topic.title.toLowerCase().includes(searchTerm.toLowerCase())
  )
  const addTopic = () => {
    const newTopic = {
      id: topics.length + 1,
      title: `New Topic ${topics.length + 1}`
    }
    setTopics([...topics, newTopic])
  }
  const deleteTopic = (id: number) => {
    setTopics(topics.filter(topic => topic.id !== id))
  }
  return (
    <div className={`w-full max-w-md mx-auto mt-4 ${className}`}>
      <div className="mb-4">
        <div className="relative">
          <Input
            type="text"
            placeholder="Search chats..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full"
          />
          <MenubarShortcut className="absolute top-1/2 right-4 transform -translate-y-1/2">
            ⌘K
          </MenubarShortcut>
        </div>
      </div>
      <ScrollArea className="space-y-2 h-[600px]">
        <div className="p-4">
          {filteredTopics.map(topic => (
            <React.Fragment key={topic.id}>
              <div className="text-sm flex hover:cursor-pointer items-center justify-between bg-gray-100 dark:bg-gray-800 rounded-md px-4 py-2 group">
                {topic.title.length > 25
                  ? `${topic.title.substring(0, 25)}...`
                  : topic.title}{' '}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => deleteTopic(topic.id)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <TrashIcon className="w-5 h-5" />
                </Button>
              </div>
              <Separator className="my-2" />
            </React.Fragment>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}

function TrashIcon(props: JSX.IntrinsicAttributes & SVGProps<SVGSVGElement>) {
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
      <path d="M3 6h18" />
      <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
    </svg>
  )
}
