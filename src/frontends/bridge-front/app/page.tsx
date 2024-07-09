import { Chat } from '@/components/chat'
import { nanoid } from 'ai'
import { AI } from './actions'
import Header from '@/components/header'


export const maxDuration = 60

export default function Page() {
  const id = nanoid()
  return (
    <div>
           <Header /> 

<AI initialAIState={{ chatId: id, messages: [] }}>
      <Chat id={id} />
    </AI>
    </div>
    
  )
}
