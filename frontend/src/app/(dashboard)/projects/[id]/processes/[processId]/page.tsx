'use client'

import dynamic from 'next/dynamic'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import {
  ChevronLeft,
  ChevronDown,
  Download,
  History,
  Loader2,
  AlertTriangle,
  RefreshCw,
  PanelRight,
  X,
} from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { Process, ProcessVersion } from '@/types'
import { Button } from '@/components/ui/button'
import { StatusBadge } from '@/components/ui/status-badge'
import { ChatWindow } from '@/components/chat/ChatWindow'
import { DocsPanel } from '@/components/bpmn/DocsPanel'
import { TranscriptionPanel } from '@/components/bpmn/TranscriptionPanel'
import { BottleneckPanel } from '@/components/bpmn/BottleneckPanel'
import { BpmnToolbar, type PresentationSpeed } from '@/components/bpmn/BpmnToolbar'
import type { BpmnViewerHandle, PresentationStatus } from '@/components/bpmn/BpmnViewer'
import { Skeleton } from '@/components/ui/skeleton'
import { Dialog } from '@/components/ui/dialog'
import { exportBpmnAsPdf, exportBpmnAsPng } from '@/lib/bpmnExport'

// bpmn-js is browser-only
const BpmnViewer = dynamic(() => import('@/components/bpmn/BpmnViewer').then((m) => m.BpmnViewer), {
  ssr: false,
  loading: () => <Skeleton className="h-full w-full" />,
})

const RIGHT_TABS = [
  { key: 'chat', label: 'Chat' },
  { key: 'docs', label: 'Documentação' },
  { key: 'bottlenecks', label: 'Sugestões' },
  { key: 'transcription', label: 'Transcrição' },
] as const
type RightTab = (typeof RIGHT_TABS)[number]['key']

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
  const [previewVersion, setPreviewVersion] = useState<ProcessVersion | null>(null)

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
    <>
      <div className="flex flex-col gap-2">
        {loading
          ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)
          : versions.map((v) => (
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
                <div className="flex shrink-0 items-center gap-1">
                  <Button variant="ghost" className="text-xs" onClick={() => setPreviewVersion(v)}>
                    Visualizar
                  </Button>
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
              </div>
            ))}
      </div>

      <Dialog
        open={previewVersion !== null}
        onClose={() => setPreviewVersion(null)}
        title={previewVersion ? `Versão ${previewVersion.version}` : ''}
        className="max-w-4xl"
      >
        {previewVersion && (
          <div className="flex flex-col gap-3">
            <div className="h-[60vh] w-full rounded-lg border border-gray-200 bg-gray-50">
              <BpmnViewer xml={previewVersion.bpmn_xml} className="h-full w-full" />
            </div>
            {previewVersion.version !== currentVersion && (
              <Button
                variant="ghost"
                className="self-end text-xs"
                loading={restoring === previewVersion.version}
                onClick={() => restore(previewVersion)}
              >
                Restaurar esta versão
              </Button>
            )}
          </div>
        )}
      </Dialog>
    </>
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
  const [rightTab, setRightTab] = useState<RightTab>('chat')
  const [highlightIds, setHighlightIds] = useState<string[]>([])
  const [presentationStatus, setPresentationStatus] = useState<PresentationStatus>('stopped')
  const [presentationSpeed, setPresentationSpeed] = useState<PresentationSpeed>(1)
  const [exportMenuOpen, setExportMenuOpen] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [rightPanelOpen, setRightPanelOpen] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const bpmnViewerRef = useRef<BpmnViewerHandle>(null)

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
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [procStatus, processId, loadProcess])

  const handleBpmnUpdate = useCallback((xml: string, version: number) => {
    setBpmnXml(xml)
    setProc((prev) => (prev ? { ...prev, bpmn_xml: xml, version } : prev))
    setPresentationStatus('stopped')
  }, [])

  const handleVersionRestore = useCallback((v: ProcessVersion) => {
    setBpmnXml(v.bpmn_xml)
    setProc((prev) => (prev ? { ...prev, bpmn_xml: v.bpmn_xml, version: v.version } : prev))
    setShowVersions(false)
    setPresentationStatus('stopped')
  }, [])

  const handleExport = useCallback(
    async (format: 'bpmn' | 'png' | 'pdf') => {
      setExportMenuOpen(false)
      setExporting(true)
      setError('')
      try {
        if (format === 'bpmn') {
          await api.processes.export(processId)
          return
        }
        const svg = await bpmnViewerRef.current?.exportSvg()
        if (!svg) throw new Error('Diagrama ainda não está pronto para exportar')
        const filename = `${proc?.name ?? 'processo'}.${format}`
        if (format === 'png') {
          await exportBpmnAsPng(svg, filename)
        } else {
          await exportBpmnAsPdf(svg, filename)
        }
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Erro ao exportar diagrama')
      } finally {
        setExporting(false)
      }
    },
    [processId, proc?.name]
  )

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
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-y-2 border-b border-gray-200 bg-white px-4 py-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <button
            onClick={() => router.push(`/projects/${projectId}`)}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
            title="Voltar ao projeto"
          >
            <ChevronLeft size={16} />
            <span className="hidden md:inline">Projeto</span>
          </button>
          <span className="hidden text-gray-300 md:inline">/</span>
          <span className="max-w-[120px] truncate text-sm font-medium text-gray-900 sm:max-w-[200px]">
            {proc.name}
          </span>
          <StatusBadge status={proc.status} />
          {isProcessing && <Loader2 size={14} className="animate-spin text-blue-500" />}
        </div>
        <div className="flex items-center gap-2">
          {isReady && (
            <>
              <Button
                variant="ghost"
                className="gap-1 text-xs lg:hidden"
                onClick={() => setRightPanelOpen(true)}
              >
                <PanelRight size={14} />
                Painel
              </Button>
              <Button
                variant="ghost"
                className="gap-1 text-xs"
                onClick={() => setShowVersions(true)}
              >
                <History size={14} />
                Versões
              </Button>
              <div className="relative">
                <button
                  onClick={() => setExportMenuOpen((v) => !v)}
                  disabled={exporting}
                  className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100 disabled:opacity-50"
                >
                  {exporting ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Download size={14} />
                  )}
                  Exportar
                  <ChevronDown size={12} />
                </button>
                {exportMenuOpen && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setExportMenuOpen(false)} />
                    <div className="absolute right-0 top-full z-20 mt-1 w-36 overflow-hidden rounded-lg border border-gray-200 bg-white py-1 shadow-md">
                      <button
                        onClick={() => handleExport('bpmn')}
                        className="block w-full px-3 py-2 text-left text-xs text-gray-700 hover:bg-gray-100"
                      >
                        .bpmn (XML)
                      </button>
                      <button
                        onClick={() => handleExport('png')}
                        className="block w-full px-3 py-2 text-left text-xs text-gray-700 hover:bg-gray-100"
                      >
                        PNG
                      </button>
                      <button
                        onClick={() => handleExport('pdf')}
                        className="block w-full px-3 py-2 text-left text-xs text-gray-700 hover:bg-gray-100"
                      >
                        PDF
                      </button>
                    </div>
                  </>
                )}
              </div>
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
              {proc.error_message && (
                <p className="max-w-md text-sm text-gray-500">{proc.error_message}</p>
              )}
              <Button variant="ghost" className="gap-1" onClick={() => window.location.reload()}>
                <RefreshCw size={14} />
                Tentar novamente
              </Button>
            </div>
          )}
          {isReady && bpmnXml && (
            <div className="relative h-full w-full">
              <BpmnViewer
                viewerRef={bpmnViewerRef}
                xml={bpmnXml}
                className="h-full w-full"
                highlightIds={highlightIds}
                presentation={{ status: presentationStatus, speed: presentationSpeed }}
              />
              <div className="absolute right-3 top-3 z-10">
                <BpmnToolbar
                  playing={presentationStatus === 'playing'}
                  speed={presentationSpeed}
                  onTogglePlay={() =>
                    setPresentationStatus((s) => (s === 'playing' ? 'paused' : 'playing'))
                  }
                  onSpeedChange={setPresentationSpeed}
                  onStop={() => setPresentationStatus('stopped')}
                />
              </div>
            </div>
          )}
        </div>

        {/* Right Panel: Chat + Docs tabs — drawer em telas <lg, painel fixo em lg+ */}
        {isReady && (
          <>
            {rightPanelOpen && (
              <div
                className="fixed inset-0 z-20 bg-black/30 lg:hidden"
                onClick={() => setRightPanelOpen(false)}
              />
            )}
            <div
              className={`fixed inset-y-0 right-0 z-30 flex w-80 max-w-[85vw] flex-col border-l border-gray-200 bg-white shadow-xl transition-transform duration-200 ease-in-out lg:static lg:z-auto lg:w-80 lg:max-w-none lg:shrink-0 lg:translate-x-0 lg:shadow-none xl:w-96 ${
                rightPanelOpen ? 'translate-x-0' : 'translate-x-full'
              }`}
            >
              <div className="flex items-center justify-between border-b border-gray-200 px-3 py-2 lg:hidden">
                <span className="text-xs font-semibold text-gray-500">Painel</span>
                <button
                  onClick={() => setRightPanelOpen(false)}
                  className="p-1 text-gray-400 hover:text-gray-600"
                >
                  <X size={16} />
                </button>
              </div>
              <div className="flex border-b border-gray-200">
                {RIGHT_TABS.map(({ key, label }) => (
                  <button
                    key={key}
                    onClick={() => {
                      setRightTab(key)
                      setHighlightIds([])
                    }}
                    className={`flex-1 py-2 text-xs font-medium transition-colors ${
                      rightTab === key
                        ? 'border-b-2 border-blue-600 text-blue-600'
                        : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="flex flex-1 flex-col overflow-hidden min-h-0">
                {rightTab === 'chat' && (
                  <ChatWindow processId={processId} onBpmnUpdate={handleBpmnUpdate} />
                )}
                {rightTab === 'docs' && <DocsPanel processId={processId} />}
                {rightTab === 'bottlenecks' && (
                  <BottleneckPanel processId={processId} onHighlight={setHighlightIds} />
                )}
                {rightTab === 'transcription' && (
                  <TranscriptionPanel transcription={proc.transcription} />
                )}
              </div>
            </div>
          </>
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
