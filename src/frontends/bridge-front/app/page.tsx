import { Chat } from '@/components/chat'
import { nanoid } from 'ai'
import { AI } from './actions'
import Header from '@/components/header'
import { ClerkProvider, SignOutButton } from '@clerk/nextjs'



export const maxDuration = 60

export default function Page() {
  const id = nanoid()
  return (
    <div>
           <Header /> 
           <SignOutButton/>

<AI initialAIState={{ chatId: id, messages: [] }}>
      <Chat id={id} />
    </AI>
    </div>
    
  )
}
