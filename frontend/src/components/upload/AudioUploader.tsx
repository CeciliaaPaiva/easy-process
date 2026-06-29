'use client'

import { useCallback, useRef, useState } from 'react'
import { Upload, FileAudio, X } from 'lucide-react'
import { clsx } from 'clsx'
import { api, ApiError } from '@/lib/api'
import type { Process } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'

const ACCEPTED = ['audio/mpeg', 'audio/wav', 'audio/mp4', 'audio/ogg', 'audio/x-m4a']
const MAX_SIZE_MB = 100

interface Props {
  projectId: string
  onUploaded: (process: Process) => void
}

export function AudioUploader({ projectId, onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [progress, setProgress] = useState(0)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)

  const validate = (f: File): string | null => {
    if (!ACCEPTED.includes(f.type) && !f.name.match(/\.(mp3|wav|m4a|ogg)$/i)) {
      return 'Formato não suportado. Use MP3, WAV, M4A ou OGG.'
    }
    if (f.size > MAX_SIZE_MB * 1024 * 1024) {
      return `Arquivo muito grande. Máximo ${MAX_SIZE_MB}MB.`
    }
    return null
  }

  const pickFile = (f: File) => {
    const err = validate(f)
    if (err) { setError(err); return }
    setError('')
    setFile(f)
    if (!name) setName(f.name.replace(/\.[^.]+$/, ''))
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) pickFile(f)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file || !name.trim()) return
    setUploading(true)
    setError('')
    try {
      const process = await api.processes.upload(projectId, name.trim(), file, setProgress)
      onUploaded(process)
      setFile(null)
      setName('')
      setProgress(0)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erro ao fazer upload')
    } finally {
      setUploading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div
        className={clsx(
          'rounded-xl border-2 border-dashed p-8 text-center transition-colors',
          dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400',
          file && 'border-green-300 bg-green-50'
        )}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !file && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && !file && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".mp3,.wav,.m4a,.ogg,audio/*"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) pickFile(f) }}
        />
        {file ? (
          <div className="flex items-center justify-center gap-3">
            <FileAudio size={24} className="text-green-600" />
            <div className="text-left">
              <p className="font-medium text-gray-900">{file.name}</p>
              <p className="text-xs text-gray-500">{(file.size / (1024 * 1024)).toFixed(1)} MB</p>
            </div>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); setFile(null); setName('') }}
              className="ml-2 rounded-full p-1 text-gray-400 hover:bg-gray-200"
            >
              <X size={14} />
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload size={32} className="text-gray-300" />
            <p className="text-sm text-gray-500">
              Arraste um áudio ou <span className="text-blue-600 underline">clique para selecionar</span>
            </p>
            <p className="text-xs text-gray-400">MP3, WAV, M4A, OGG • máx {MAX_SIZE_MB}MB</p>
          </div>
        )}
      </div>

      {file && (
        <Input
          label="Nome do processo"
          placeholder="Ex: Entrevista com gerente de RH"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
      )}

      {uploading && <Progress value={progress} label="Enviando..." />}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {file && (
        <Button type="submit" loading={uploading} disabled={!name.trim()}>
          Iniciar processamento
        </Button>
      )}
    </form>
  )
}
