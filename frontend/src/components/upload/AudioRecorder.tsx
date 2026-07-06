'use client'

import { useEffect, useRef, useState } from 'react'
import { Mic, Square, Trash2 } from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/button'

// Deve espelhar MAX_AUDIO_DURATION_MINUTES em backend/app/core/config.py —
// o backend também valida e rejeita, isso aqui só evita gravar além do limite.
export const MAX_RECORDING_SECONDS = 30 * 60

const PREFERRED_MIME_TYPES = ['audio/webm;codecs=opus', 'audio/webm']

function pickMimeType(): string {
  for (const mime of PREFERRED_MIME_TYPES) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(mime)) {
      return mime
    }
  }
  return 'audio/webm'
}

function formatTime(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, '0')
  const seconds = (totalSeconds % 60).toString().padStart(2, '0')
  return `${minutes}:${seconds}`
}

interface Props {
  onRecorded: (file: File) => void
}

export function AudioRecorder({ onRecorded }: Props) {
  const [supported, setSupported] = useState(true)
  const [insecureContext, setInsecureContext] = useState(false)
  const [recording, setRecording] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [error, setError] = useState('')

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const streamRef = useRef<MediaStream | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const mimeTypeRef = useRef<string>('audio/webm')

  useEffect(() => {
    const hasSupport =
      typeof navigator !== 'undefined' &&
      !!navigator.mediaDevices?.getUserMedia &&
      typeof MediaRecorder !== 'undefined'
    setSupported(hasSupport)
    // getUserMedia só existe em contexto seguro (HTTPS ou localhost) — em HTTP
    // com domínio customizado o navegador nem expõe a API, o que parece
    // "sem suporte" mas na verdade é bloqueio de contexto inseguro.
    setInsecureContext(
      !hasSupport && typeof window !== 'undefined' && !window.isSecureContext
    )

    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop())
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  const stopRecording = () => {
    mediaRecorderRef.current?.stop()
    setRecording(false)
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }

  const startRecording = async () => {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []
      mimeTypeRef.current = pickMimeType()

      const recorder = new MediaRecorder(stream, { mimeType: mimeTypeRef.current })
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeTypeRef.current })
        setPreviewUrl(URL.createObjectURL(blob))
        streamRef.current?.getTracks().forEach((track) => track.stop())
        streamRef.current = null
      }
      mediaRecorderRef.current = recorder
      recorder.start()
      setRecording(true)
      setElapsed(0)

      timerRef.current = setInterval(() => {
        setElapsed((prev) => {
          const next = prev + 1
          if (next >= MAX_RECORDING_SECONDS) {
            stopRecording()
          }
          return next
        })
      }, 1000)
    } catch {
      setError('Não foi possível acessar o microfone. Verifique as permissões do navegador.')
    }
  }

  const discard = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl(null)
    chunksRef.current = []
    setElapsed(0)
  }

  const confirm = () => {
    const blob = new Blob(chunksRef.current, { type: mimeTypeRef.current })
    const ext = mimeTypeRef.current.includes('webm') ? 'webm' : 'ogg'
    onRecorded(new File([blob], `gravacao.${ext}`, { type: mimeTypeRef.current }))
    discard()
  }

  if (!supported) {
    return (
      <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
        {insecureContext
          ? 'Gravação de áudio exige conexão segura (HTTPS) ou acesso via localhost. ' +
            'Acesse por um endereço https:// ou envie um arquivo.'
          : 'Gravação de áudio não é suportada neste navegador. Use Chrome, Firefox ou Edge, ' +
            'ou envie um arquivo.'}
      </p>
    )
  }

  return (
    <div className="flex flex-col items-center gap-4 rounded-xl border-2 border-dashed border-gray-300 p-8 text-center">
      {!previewUrl && (
        <>
          <button
            type="button"
            aria-label={recording ? 'Parar gravação' : 'Iniciar gravação'}
            onClick={recording ? stopRecording : startRecording}
            className={clsx(
              'flex h-16 w-16 items-center justify-center rounded-full text-white transition-colors',
              recording ? 'animate-pulse bg-red-500' : 'bg-blue-600 hover:bg-blue-700'
            )}
          >
            {recording ? <Square size={24} /> : <Mic size={24} />}
          </button>
          <p className="text-sm text-gray-500">
            {recording ? `Gravando... ${formatTime(elapsed)}` : 'Toque para gravar'}
          </p>
          {recording && elapsed >= MAX_RECORDING_SECONDS - 60 && (
            <p className="text-xs text-amber-600">
              Encerramento automático em breve (limite de {MAX_RECORDING_SECONDS / 60}min)
            </p>
          )}
        </>
      )}

      {previewUrl && (
        <div className="flex w-full flex-col items-center gap-3">
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <audio controls src={previewUrl} data-testid="recording-preview" className="w-full" />
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={discard}>
              <Trash2 size={14} className="mr-1" />
              Descartar
            </Button>
            <Button type="button" onClick={confirm}>
              Usar esta gravação
            </Button>
          </div>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}
