'use client'

import React, { cache, useState, useEffect } from 'react'
import HistoryItem from './history-item'
import { Chat } from '@/lib/types'
import { getChats } from '@/lib/actions/chat'
import { ClearHistory } from './clear-history'
import { Input } from '@/components/ui/input'
import { MenubarShortcut } from '@/components/ui/menubar'

type HistoryListProps = {
  userId?: string
}

const loadChats = cache(async (userId?: string) => {
  return await getChats(userId)
})

// Start of Selection
export function HistoryList({ userId }: HistoryListProps) {
  const [chats, setChats] = useState<Chat[]>([])
  const [searchTerm, setSearchTerm] = useState('')

  useEffect(() => {
    loadChats(userId).then(chats => setChats(chats))
  }, [userId])

  const filteredChats = chats.filter(chat =>
    chat.title.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="flex flex-col flex-1 space-y-3 h-full">
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
      <div className="flex flex-col space-y-0.5 flex-1 overflow-y-auto">
        {!chats?.length ? (
          <div className="text-foreground/30 text-sm text-center py-4">
            No search history
          </div>
        ) : (
          filteredChats?.map(
            (chat: Chat) => chat && <HistoryItem key={chat.id} chat={chat} />
          )
        )}
      </div>
      <div className="mt-auto">
        <ClearHistory empty={!chats?.length} />
      </div>
    </div>
  )
}
