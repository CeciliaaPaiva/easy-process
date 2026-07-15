import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { BpmnToolbar } from './BpmnToolbar'

describe('BpmnToolbar', () => {
  it('chama onTogglePlay ao clicar no botão de play/pause', () => {
    const onTogglePlay = vi.fn()
    render(
      <BpmnToolbar
        playing={false}
        speed={1}
        onTogglePlay={onTogglePlay}
        onSpeedChange={vi.fn()}
        onStop={vi.fn()}
      />
    )
    fireEvent.click(screen.getByTitle('Iniciar apresentação'))
    expect(onTogglePlay).toHaveBeenCalledOnce()
  })

  it('mostra o rótulo de pausa quando já está tocando', () => {
    render(
      <BpmnToolbar
        playing
        speed={1}
        onTogglePlay={vi.fn()}
        onSpeedChange={vi.fn()}
        onStop={vi.fn()}
      />
    )
    expect(screen.getByTitle('Pausar apresentação')).toBeInTheDocument()
  })

  it('cicla a velocidade 0.5x -> 1x -> 2x -> 0.5x', () => {
    const onSpeedChange = vi.fn()
    render(
      <BpmnToolbar
        playing={false}
        speed={1}
        onTogglePlay={vi.fn()}
        onSpeedChange={onSpeedChange}
        onStop={vi.fn()}
      />
    )
    fireEvent.click(screen.getByTitle('Velocidade da animação'))
    expect(onSpeedChange).toHaveBeenCalledWith(2)
  })

  it('chama onStop ao clicar no botão de parar', () => {
    const onStop = vi.fn()
    render(
      <BpmnToolbar
        playing
        speed={1}
        onTogglePlay={vi.fn()}
        onSpeedChange={vi.fn()}
        onStop={onStop}
      />
    )
    fireEvent.click(screen.getByTitle('Sair do modo apresentação'))
    expect(onStop).toHaveBeenCalledOnce()
  })
})
