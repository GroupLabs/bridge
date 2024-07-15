import React from 'react'
import { ModeToggle } from './mode-toggle'
import { IconLogo } from './ui/icons'
import { cn } from '@/lib/utils'
import HistoryContainer from './history-container'
import Image from 'next/image'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"

import { GearIcon } from '@radix-ui/react-icons'
import { Button } from '@/components/ui/button'
import Link from 'next/link'

// Import your SVG file
import Logo from '@/public/images/logo.svg'

export const Header: React.FC = async () => {
  return (
    <header className="w-full p-1 md:p-2 flex justify-between items-center">
        <div className='flex items-center px-4'>
          <a href="/" className="group block flex-shrink-0">
            <div className="flex items-center">
              {/* <Image src={Logo} alt="Bridge Logo" className="h-8 w-auto" /> Adjust height and width as needed */}
              <div className="text-xl font-regular">
                Bridge
              </div>
            </div>
          </a>
          {/* <ModeToggle /> */}
        </div>
      <div className="flex gap-0.5">
        <div className='flex items-center px-4'>
        <Button variant="outline" asChild>
          <Link href="/settings">Settings</Link>
        </Button>

          {/* <ModeToggle /> */}
        </div>
        <HistoryContainer location="header" />
      </div>
    </header>
  )
}

export default Header