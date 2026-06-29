import type { ProcessStatus } from '@/types'
import { Badge } from './badge'

const labels: Record<ProcessStatus, string> = {
  pending: 'Aguardando',
  transcribing: 'Transcrevendo',
  generating: 'Gerando BPMN',
  ready: 'Pronto',
  error: 'Erro',
}

const variants: Record<ProcessStatus, 'default' | 'info' | 'warning' | 'success' | 'error'> = {
  pending: 'default',
  transcribing: 'info',
  generating: 'warning',
  ready: 'success',
  error: 'error',
}

export function StatusBadge({ status }: { status: ProcessStatus }) {
  return <Badge variant={variants[status]}>{labels[status]}</Badge>
}
