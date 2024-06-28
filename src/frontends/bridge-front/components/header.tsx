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
                <MessageCircleIcon className="h-6 w-6" />
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
              <ActivityIcon className="h-6 w-6" />
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
              <BarChart2Icon className="h-6 w-6" />
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
              <AccountIcon className="h-6 w-6" />
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

function ActivityIcon(
  props: React.JSX.IntrinsicAttributes & React.SVGProps<SVGSVGElement>
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
      <path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2" />
    </svg>
  )
}

function BarChart2Icon(
  props: React.JSX.IntrinsicAttributes & React.SVGProps<SVGSVGElement>
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
      <line x1="18" x2="18" y1="20" y2="10" />
      <line x1="12" x2="12" y1="20" y2="4" />
      <line x1="6" x2="6" y1="20" y2="14" />
    </svg>
  )
}

function MessageCircleIcon(
  props: React.JSX.IntrinsicAttributes & React.SVGProps<SVGSVGElement>
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
      <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />
    </svg>
  )
}

function AccountIcon(
  props: React.JSX.IntrinsicAttributes & React.SVGProps<SVGSVGElement>
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
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  )
}

export default Header
