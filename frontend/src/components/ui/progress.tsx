import { clsx } from 'clsx'

interface ProgressProps {
  value: number
  className?: string
  label?: string
}

export function Progress({ value, className, label }: ProgressProps) {
  const clamped = Math.max(0, Math.min(100, value))
  return (
    <div className={clsx('space-y-1', className)}>
      {label && (
        <div className="flex justify-between text-xs text-gray-500">
          <span>{label}</span>
          <span>{clamped}%</span>
        </div>
      )}
      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
        <div
          className="h-full rounded-full bg-blue-600 transition-all duration-300"
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  )
}
