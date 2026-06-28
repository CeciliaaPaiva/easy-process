import { cn } from '@/lib/utils'

interface AlertProps {
  variant?: 'error' | 'success' | 'warning'
  message: string
  className?: string
}

const styles = {
  error: 'bg-red-50 border-red-200 text-red-700',
  success: 'bg-green-50 border-green-200 text-green-700',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-700',
}

export function Alert({ variant = 'error', message, className }: AlertProps) {
  return (
    <div
      role="alert"
      className={cn(
        'rounded-lg border px-4 py-3 text-sm',
        styles[variant],
        className
      )}
    >
      {message}
    </div>
  )
}
