'use client'

import dynamic from 'next/dynamic'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import {
  ChevronLeft,
  Download,
  History,
  Loader2,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { Process, ProcessVersion } from '@/types'
import { Button } from '@/components/ui/button'
import { StatusBadge } from '@/components/ui/status-badge'
import { ChatWindow } from '@/components/chat/ChatWindow'
import { DocsPanel } from '@/components/bpmn/DocsPanel'
import { Skeleton } from '@/components/ui/skeleton'
import { Dialog } from '@/components/ui/dialog'

// bpmn-js is browser-only
const BpmnViewer = dynamic(
  () => import('@/components/bpmn/BpmnViewer').then((m) => m.BpmnViewer),
  { ssr: false, loading: () => <Skeleton className="h-full w-full" /> }
)

const POLL_INTERVAL_MS = 3000
const PROCESSING_STATUSES = new Set(['pending', 'transcribing', 'generating'])

function VersionsPanel({
  processId,
  currentVersion,
  onRestore,
}: {
  processId: string
  currentVersion: number
  onRestore: (version: ProcessVersion) => void
}) {
  const [versions, setVersions] = useState<ProcessVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [restoring, setRestoring] = useState<number | null>(null)

  useEffect(() => {
    api.versions
      .list(processId)
      .then(setVersions)
      .finally(() => setLoading(false))
  }, [processId, currentVersion])

  const restore = async (v: ProcessVersion) => {
    setRestoring(v.version)
    try {
      const updated = await api.versions.restore(processId, v.version)
      const restoredVersion = await api.versions.get(processId, updated.version)
      onRestore(restoredVersion)
      const fresh = await api.versions.list(processId)
      setVersions(fresh)
    } finally {
      setRestoring(null)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {loading ? (
        Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)
      ) : (
        versions.map((v) => (
          <div
            key={v.id}
            className="flex items-center justify-between rounded-lg border border-gray-200 p-3"
          >
            <div>
              <p className="text-sm font-medium text-gray-900">Versão {v.version}</p>
              <p className="text-xs text-gray-500 line-clamp-1">
                {v.change_description ?? 'Sem descrição'}
              </p>
            </div>
            {v.version !== currentVersion && (
              <Button
                variant="ghost"
                className="text-xs"
                loading={restoring === v.version}
                onClick={() => restore(v)}
              >
                Restaurar
              </Button>
            )}
          </div>
        ))
      )}
    </div>
  )
}

export default function ProcessPage() {
  const { id: projectId, processId } = useParams<{ id: string; processId: string }>()
  const router = useRouter()

  const [proc, setProc] = useState<Process | null>(null)
  const [bpmnXml, setBpmnXml] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showVersions, setShowVersions] = useState(false)
  const [rightTab, setRightTab] = useState<'chat' | 'docs'>('chat')
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadProcess = useCallback(async () => {
    try {
      const p = await api.processes.get(processId)
      setProc(p)
      if (p.status === 'ready' && p.bpmn_xml) {
        setBpmnXml(p.bpmn_xml)
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erro ao carregar processo')
    }
  }, [processId])

  useEffect(() => {
    loadProcess().finally(() => setLoading(false))
  }, [loadProcess])

  // Poll while processing — effect re-runs when status changes
  const procStatus = proc?.status
  const procVersion = proc?.version
  useEffect(() => {
    if (!procStatus || !PROCESSING_STATUSES.has(procStatus)) return
    const snapshotStatus = procStatus
    const snapshotVersion = procVersion
    pollRef.current = setInterval(async () => {
      const { status, version } = await api.processes.status(processId)
      if (status !== snapshotStatus || version !== snapshotVersion) {
        await loadProcess()
      }
      if (!PROCESSING_STATUSES.has(status)) {
        clearInterval(pollRef.current!)
      }
    }, POLL_INTERVAL_MS)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [procStatus, processId, loadProcess])

  const handleBpmnUpdate = useCallback((xml: string, version: number) => {
    setBpmnXml(xml)
    setProc((prev) => prev ? { ...prev, bpmn_xml: xml, version } : prev)
  }, [])

  const handleVersionRestore = useCallback((v: ProcessVersion) => {
    setBpmnXml(v.bpmn_xml)
    setProc((prev) => prev ? { ...prev, bpmn_xml: v.bpmn_xml, version: v.version } : prev)
    setShowVersions(false)
  }, [])

  if (loading) {
    return (
      <div className="flex h-full flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="flex-1" />
      </div>
    )
  }

  if (error || !proc) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error || 'Processo não encontrado'}
      </div>
    )
  }

  const isProcessing = PROCESSING_STATUSES.has(proc.status)
  const isReady = proc.status === 'ready'
  const hasError = proc.status === 'error'

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col gap-0 -m-8">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b border-gray-200 bg-white px-6 py-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push(`/projects/${projectId}`)}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
          >
            <ChevronLeft size={16} />
            Projeto
          </button>
          <span className="text-gray-300">/</span>
          <span className="max-w-[200px] truncate text-sm font-medium text-gray-900">
            {proc.name}
          </span>
          <StatusBadge status={proc.status} />
          {isProcessing && (
            <Loader2 size={14} className="animate-spin text-blue-500" />
          )}
        </div>
        <div className="flex items-center gap-2">
          {isReady && (
            <>
              <Button
                variant="ghost"
                className="gap-1 text-xs"
                onClick={() => setShowVersions(true)}
              >
                <History size={14} />
                Versões
              </Button>
              <a
                href={api.processes.export(processId)}
                download
                className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100"
              >
                <Download size={14} />
                Exportar
              </a>
            </>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* BPMN Viewer */}
        <div className="flex flex-1 flex-col items-center justify-center overflow-hidden bg-gray-50">
          {isProcessing && (
            <div className="flex flex-col items-center gap-3 text-center">
              <Loader2 size={40} className="animate-spin text-blue-500" />
              <p className="font-medium text-gray-700">
                {proc.status === 'pending' && 'Aguardando processamento...'}
                {proc.status === 'transcribing' && 'Transcrevendo áudio...'}
                {proc.status === 'generating' && 'Gerando diagrama BPMN...'}
              </p>
              <p className="text-sm text-gray-400">Isso pode levar alguns minutos</p>
            </div>
          )}
          {hasError && (
            <div className="flex flex-col items-center gap-3 text-center">
              <AlertTriangle size={40} className="text-red-400" />
              <p className="font-medium text-gray-700">Erro no processamento</p>
              <Button
                variant="ghost"
                className="gap-1"
                onClick={() => window.location.reload()}
              >
                <RefreshCw size={14} />
                Tentar novamente
              </Button>
            </div>
          )}
          {isReady && bpmnXml && (
            <BpmnViewer xml={bpmnXml} className="h-full w-full" />
          )}
        </div>

        {/* Right Panel: Chat + Docs tabs */}
        {isReady && (
          <div className="flex w-80 shrink-0 flex-col border-l border-gray-200 bg-white">
            <div className="flex border-b border-gray-200">
              {(['chat', 'docs'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setRightTab(tab)}
                  className={`flex-1 py-2 text-xs font-medium transition-colors ${
                    rightTab === tab
                      ? 'border-b-2 border-blue-600 text-blue-600'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {tab === 'chat' ? 'Chat' : 'Documentação'}
                </button>
              ))}
            </div>
            <div className="flex-1 overflow-hidden">
              {rightTab === 'chat' ? (
                <ChatWindow processId={processId} onBpmnUpdate={handleBpmnUpdate} />
              ) : (
                <DocsPanel processId={processId} />
              )}
            </div>
          </div>
        )}
      </div>

      {/* Versions Dialog */}
      <Dialog
        open={showVersions}
        onClose={() => setShowVersions(false)}
        title="Histórico de versões"
        className="max-w-md"
      >
        <VersionsPanel
          processId={processId}
          currentVersion={proc.version}
          onRestore={handleVersionRestore}
        />
      </Dialog>
    </div>
  )
}
