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
    <header className="fixed w-full p-1 md:p-2 flex justify-between items-center z-10 backdrop-blur md:backdrop-blur-none bg-background/80 md:bg-transparent">
      <div>
        <a href="/">
          <IconLogo className={cn('w-5 h-5')} />
          <span className="sr-only">Bridge</span>
        </a>
      </div>
      <div className="flex gap-0.5">
        <div className='flex items-center px-4'>
          <a href="#" className="group block flex-shrink-0">
            <div className="flex items-center">
              <AddData />
            </div>
          </a>


          {/* <ModeToggle /> */}
        </div>
        <HistoryContainer location="header" />
      </div>
    </header>
  )
}

export default Header
