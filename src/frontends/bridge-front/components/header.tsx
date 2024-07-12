import React from 'react'
import { ModeToggle } from './mode-toggle'
import { IconLogo } from './ui/icons'
import { cn } from '@/lib/utils'
import HistoryContainer from './history-container'
import { AddData } from './add-data'


import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"

export const Header: React.FC = async () => {
  return (
    <header className="w-full p-1 md:p-2 flex justify-between items-center">
        <div className='flex items-center px-4'>
          <a href="#" className="group block flex-shrink-0">
            <div className="flex items-center">
              Bridge
            </div>
          </a>
          {/* <ModeToggle /> */}
        </div>
      <div className="flex gap-0.5">
        <div className='flex items-center px-4'>
          <div className="group block flex-shrink-0">
            <div className="flex items-center">
              Settings
            </div>
          </div>
          {/* <ModeToggle /> */}
        </div>
        <HistoryContainer location="header" />
      </div>
    </header>
  )
}

export default Header
