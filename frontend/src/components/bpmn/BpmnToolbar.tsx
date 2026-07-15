'use client'

import { Pause, Play, Square } from 'lucide-react'

export const PRESENTATION_SPEEDS = [0.5, 1, 2] as const
export type PresentationSpeed = (typeof PRESENTATION_SPEEDS)[number]

interface Props {
  playing: boolean
  speed: PresentationSpeed
  onTogglePlay: () => void
  onSpeedChange: (speed: PresentationSpeed) => void
  onStop: () => void
}

export function BpmnToolbar({ playing, speed, onTogglePlay, onSpeedChange, onStop }: Props) {
  const cycleSpeed = () => {
    const idx = PRESENTATION_SPEEDS.indexOf(speed)
    onSpeedChange(PRESENTATION_SPEEDS[(idx + 1) % PRESENTATION_SPEEDS.length])
  }

  return (
    <div className="flex items-center gap-1 rounded-lg border border-gray-200 bg-white p-1 shadow-sm">
      <button
        onClick={onTogglePlay}
        title={playing ? 'Pausar apresentação' : 'Iniciar apresentação'}
        className="inline-flex h-8 w-8 items-center justify-center rounded-md text-gray-600 hover:bg-gray-100"
      >
        {playing ? <Pause size={16} /> : <Play size={16} />}
      </button>
      <button
        onClick={cycleSpeed}
        title="Velocidade da animação"
        className="inline-flex h-8 min-w-8 items-center justify-center rounded-md px-2 text-xs font-semibold text-gray-600 hover:bg-gray-100"
      >
        {speed}x
      </button>
      <button
        onClick={onStop}
        title="Sair do modo apresentação"
        className="inline-flex h-8 w-8 items-center justify-center rounded-md text-gray-600 hover:bg-gray-100"
      >
        <Square size={14} />
      </button>
    </div>
  )
}
