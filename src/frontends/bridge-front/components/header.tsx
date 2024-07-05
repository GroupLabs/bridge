import React from 'react'
import { ModeToggle } from './mode-toggle'
import { IconLogo } from './ui/icons'
import { cn } from '@/lib/utils'
import HistoryContainer from './history-container'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import {
  Menubar,
  MenubarContent,
  MenubarItem,
  MenubarMenu,
  MenubarRadioGroup,
  MenubarRadioItem,
  MenubarSeparator,
  MenubarShortcut,
  MenubarTrigger
} from '@/components/ui/menubar'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger
} from '@/components/ui/sheet'
import { Chats } from '@/components/chats'
import { MessageSquareText, LineChart, HardDrive, User } from 'lucide-react'

export const Header: React.FC = async () => {
  return (
    <header className="flex items-center justify-center h-16 px-4 border-b shrink-0 md:px-6">
      <nav className="flex w-full justify-between items-between lg:px-10">
        <div>
          <a href="/">
            <IconLogo className={cn('w-5 h-5')} />
            <span className="sr-only">Bridge</span>
          </a>
        </div>
        <Menubar>
          <MenubarMenu>
            <Sheet>
              <SheetTrigger className="flex gap-2 lg:px-10 lg:py-0 hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-gray-50">
                <MessageSquareText size={24} />
                Chat
              </SheetTrigger>
              <SheetContent>
                <SheetHeader>
                  <SheetTitle>Chat History</SheetTitle>
                  <SheetDescription>
                    <a href="/">
                      <Button className="w-full mt-6">
                        New Chat <MenubarShortcut>⌘T</MenubarShortcut>
                      </Button>
                    </a>
                    <Chats className="mt-4" />
                  </SheetDescription>
                </SheetHeader>
              </SheetContent>
            </Sheet>
          </MenubarMenu>
          <MenubarMenu>
            <MenubarTrigger className="gap-2 lg:px-10 py-0">
              <LineChart size={24} />
              Insights
            </MenubarTrigger>
            <MenubarContent>
              <MenubarItem>
                View Insights <MenubarShortcut>⌘I</MenubarShortcut>
              </MenubarItem>
            </MenubarContent>
          </MenubarMenu>
          <MenubarMenu>
            <MenubarTrigger className="gap-2 lg:px-10 py-0">
              <HardDrive size={24} />
              Data
            </MenubarTrigger>
            <MenubarContent>
              <a href="/files">
                <MenubarItem>
                  Files <MenubarShortcut>⌘U</MenubarShortcut>
                </MenubarItem>
              </a>
              <a href="/connectors">
                <MenubarItem>
                  Connectors <MenubarShortcut>⌘C</MenubarShortcut>
                </MenubarItem>
              </a>
              <a href="/databases">
                <MenubarItem>
                  Databases <MenubarShortcut>⌘D</MenubarShortcut>
                </MenubarItem>
              </a>
            </MenubarContent>
          </MenubarMenu>
          <MenubarMenu>
            <MenubarTrigger className="gap-2 lg:px-10 py-0">
              <User size={24} />
              Account
            </MenubarTrigger>
            <MenubarContent>
              <MenubarRadioGroup value="benoit">
                <MenubarRadioItem value="andy">Noah</MenubarRadioItem>
                <MenubarRadioItem value="benoit">Daniil</MenubarRadioItem>
                <MenubarRadioItem value="Luis">Noel</MenubarRadioItem>
              </MenubarRadioGroup>
              <MenubarSeparator />
              <MenubarItem inset disabled>
                Add Profile...
              </MenubarItem>
              <MenubarSeparator />
              <MenubarItem inset>Settings</MenubarItem>
              <MenubarSeparator />
              <MenubarItem inset>Logout</MenubarItem>
            </MenubarContent>
          </MenubarMenu>
        </Menubar>

        <div className="flex gap-0.5">
          <ModeToggle />
          {/* <HistoryContainer location="header" /> */}
        </div>
      </nav>
    </header>
  )
}

export default Header
