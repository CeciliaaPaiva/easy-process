import { FileAudio } from 'lucide-react'

export function TranscriptionPanel({ transcription }: { transcription?: string | null }) {
  if (!transcription) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <FileAudio size={32} className="text-gray-300" />
        <p className="text-sm text-gray-500">Nenhuma transcrição disponível</p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4 text-sm">
      <h3 className="font-semibold text-gray-900">Transcrição do áudio</h3>
      <p className="whitespace-pre-wrap leading-relaxed text-gray-600">{transcription}</p>
    </div>
  )
}
