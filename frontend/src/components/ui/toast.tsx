'use client'

import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { clsx } from 'clsx'
import { CheckCircle, AlertCircle, Info, X } from 'lucide-react'

type ToastVariant = 'success' | 'error' | 'info'

interface Toast {
  id: string
  message: string
  variant: ToastVariant
}

interface ToastContextValue {
  toast: (message: string, variant?: ToastVariant) => void
}

const ToastContext = createContext<ToastContextValue>({ toast: () => {} })

const icons: Record<ToastVariant, React.ReactNode> = {
  success: <CheckCircle size={16} className="text-green-600" />,
  error: <AlertCircle size={16} className="text-red-600" />,
  info: <Info size={16} className="text-blue-600" />,
}

const styles: Record<ToastVariant, string> = {
  success: 'border-green-200 bg-green-50 text-green-900',
  error: 'border-red-200 bg-red-50 text-red-900',
  info: 'border-blue-200 bg-blue-50 text-blue-900',
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    const timer = timers.current.get(id)
    if (timer) { clearTimeout(timer); timers.current.delete(id) }
  }, [])

  const toast = useCallback((message: string, variant: ToastVariant = 'info') => {
    const id = crypto.randomUUID()
    setToasts((prev) => [...prev.slice(-4), { id, message, variant }])
    const timer = setTimeout(() => dismiss(id), 4000)
    timers.current.set(id, timer)
  }, [dismiss])

  useEffect(() => {
    const map = timers.current
    return () => { map.forEach(clearTimeout) }
  }, [])

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={clsx(
              'flex min-w-[280px] max-w-sm items-start gap-2 rounded-lg border px-4 py-3 shadow-lg',
              'animate-in slide-in-from-right-4 duration-200',
              styles[t.variant]
            )}
          >
            {icons[t.variant]}
            <span className="flex-1 text-sm">{t.message}</span>
            <button onClick={() => dismiss(t.id)} className="shrink-0 opacity-60 hover:opacity-100">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}
