'use client'

import { useEffect, useRef, useState } from 'react'
import { Send, Bot, User } from 'lucide-react'
import { clsx } from 'clsx'
import { api, ApiError } from '@/lib/api'
import type { ChatMessage } from '@/types'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

interface Props {
  processId: string
  onBpmnUpdate: (xml: string, version: number) => void
}

export function ChatWindow({ processId, onBpmnUpdate }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.chat
      .history(processId)
      .then(setMessages)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [processId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || sending) return
    const text = input.trim()
    setInput('')
    setSending(true)
    setError('')

    const optimistic: ChatMessage = {
      id: crypto.randomUUID(),
      process_id: processId,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, optimistic])

    try {
      const res = await api.chat.send(processId, text)
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== optimistic.id),
        res.user_message,
        res.assistant_message,
      ])
      onBpmnUpdate(res.bpmn_xml, res.version)
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id))
      setError(err instanceof ApiError ? err.message : 'Erro ao enviar mensagem')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-gray-200 px-4 py-3">
        <h3 className="text-sm font-semibold text-gray-900">Refinamento via chat</h3>
        <p className="text-xs text-gray-500">Peça ajustes em linguagem natural</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {loading ? (
          <>
            <Skeleton className="h-10 w-3/4" />
            <Skeleton className="ml-auto h-10 w-2/3" />
          </>
        ) : messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 py-8 text-center text-sm text-gray-400">
            <Bot size={32} className="text-gray-200" />
            <p>Envie uma instrução para refinar o diagrama</p>
            <p className="text-xs">Ex: &quot;Adicione um gateway de aprovação após a tarefa 2&quot;</p>
          </div>
        ) : (
          messages.map((m) => (
            <div
              key={m.id}
              className={clsx(
                'flex gap-2',
                m.role === 'user' ? 'flex-row-reverse' : 'flex-row'
              )}
            >
              <div
                className={clsx(
                  'flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-white',
                  m.role === 'user' ? 'bg-blue-600' : 'bg-gray-500'
                )}
              >
                {m.role === 'user' ? <User size={14} /> : <Bot size={14} />}
              </div>
              <div
                className={clsx(
                  'max-w-[80%] rounded-2xl px-3 py-2 text-sm',
                  m.role === 'user'
                    ? 'rounded-tr-none bg-blue-600 text-white'
                    : 'rounded-tl-none bg-gray-100 text-gray-900'
                )}
              >
                {m.content}
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {error && (
        <p className="px-4 pb-2 text-xs text-red-600">{error}</p>
      )}

      <form onSubmit={send} className="border-t border-gray-200 p-3 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ex: Adicione um gateway de aprovação..."
          className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          disabled={sending}
        />
        <Button
          type="submit"
          disabled={!input.trim() || sending}
          loading={sending}
          className="shrink-0 px-3"
        >
          <Send size={16} />
        </Button>
      </form>
    </div>
  )
}
