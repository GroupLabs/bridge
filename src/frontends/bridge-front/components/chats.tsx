import React from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { HistoryList } from './history-list'

export interface ChatsProps {
  className?: string
}

export function Chats({ className }: ChatsProps) {
  return (
    <div className={`w-full max-w-md mx-auto mt-4 ${className}`}>
      <ScrollArea className="space-y-2 h-[600px]">
        <HistoryList userId="anonymous" />
      </ScrollArea>
    </div>
  )
}
