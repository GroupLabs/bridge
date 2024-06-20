'use client'

import { useEffect, useState, useRef, JSX, SVGProps } from 'react'
import { useRouter } from 'next/navigation'
import type { AI, UIState } from '@/app/actions'
import { useUIState, useActions } from 'ai/rsc'
import { cn } from '@/lib/utils'
import { UserMessage } from './user-message'
import { Button } from './ui/button'
import { ArrowRight, Plus } from 'lucide-react'
import { EmptyScreen } from './empty-screen'
import { Input } from '@/components/ui/input'
import { nanoid } from 'ai'

interface ChatPanelProps {
  messages: UIState
  query?: string
}

export function ChatPanel({ messages, query }: ChatPanelProps) {
  const [input, setInput] = useState('')
  const [showEmptyScreen, setShowEmptyScreen] = useState(false)
  const [, setMessages] = useUIState<typeof AI>()
  const { submit } = useActions()
  const router = useRouter()
  const inputRef = useRef<HTMLInputElement>(null)
  const isFirstRender = useRef(true)

  async function handleQuerySubmit(query: string) {
    setInput(query)

    // Add user message to UI state
    setMessages(currentMessages => [
      ...currentMessages,
      {
        id: nanoid(),
        component: <UserMessage message={query} />
      }
    ])

    // Submit and get response message
    const data = new FormData()
    data.append('input', query)
    const responseMessage = await submit(data)
    setMessages(currentMessages => [...currentMessages, responseMessage])
  }

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    await handleQuerySubmit(input)
    setInput('') // Clear the input field after submission
  }

  useEffect(() => {
    if (isFirstRender.current && query && query.trim().length > 0) {
      handleQuerySubmit(query)
      isFirstRender.current = false
    }
  }, [query])

  const handleClear = () => {
    setMessages([]) // Clear the messages state
    setInput('') // Clear the input state
    router.push('/') // Update the URL
  }

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  if (messages.length > 0) {
    return (
      <div className="fixed bottom-2 md:bottom-8 left-0 right-0 flex justify-center items-center mx-auto pointer-events-none">
        <Button
          type="button"
          variant={'secondary'}
          className="rounded-full bg-secondary/80 group transition-all hover:scale-105 pointer-events-auto"
          onClick={() => handleClear()}
        >
          <span className="text-sm mr-2 group-hover:block hidden animate-in fade-in duration-300">
            New
          </span>
          <Plus size={18} className="group-hover:rotate-90 transition-all" />
        </Button>
      </div>
    )
  }

  if (query && query.trim().length > 0) {
    return null
  }

  return (
    <div className={'flex flex-col items-center justify-center'}>
      <form onSubmit={handleSubmit} className="max-w-2xl w-full px-6">
        <div className="relative mt-56 flex items-center justify-center w-full">
          <Input
            ref={inputRef}
            type="text"
            placeholder="How can I help you?"
            value={input}
            className="border-b-2 border-gray-900 shadow-2xl text-xl w-full h-12 p-6 text-lg rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-300"
            onChange={e => {
              setInput(e.target.value)
              setShowEmptyScreen(e.target.value.length === 0)
            }}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                if (input.trim().length === 0) {
                  e.preventDefault()
                  return
                }
                e.preventDefault()
                handleQuerySubmit(input) // Ensure input is submitted correctly
              }
            }}
            onFocus={() => setShowEmptyScreen(true)}
            onBlur={() => setShowEmptyScreen(false)}
          />
          <Button
            type="submit"
            size="icon"
            className="absolute top-1/2 right-2 transform -translate-y-1/2"
            disabled={input.length === 0}
          >
            <ArrowRightIcon className="h-5 w-5" />
          </Button>
        </div>
        <EmptyScreen
          submitMessage={message => {
            setInput(message)
          }}
          className={cn(showEmptyScreen ? 'visible' : 'invisible')}
        />
      </form>
    </div>
  )
}

function ArrowRightIcon(
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
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </svg>
  )
}
