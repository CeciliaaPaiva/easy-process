import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AudioRecorder } from './AudioRecorder'

class FakeMediaRecorder {
  static isTypeSupported = vi.fn().mockReturnValue(true)
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null

  constructor(
    public stream: MediaStream,
    public options?: MediaRecorderOptions
  ) {}

  start() {
    // no-op — o estado de "gravando" é gerenciado pelo componente
  }

  stop() {
    this.ondataavailable?.({ data: new Blob(['fake-audio-bytes'], { type: 'audio/webm' }) })
    this.onstop?.()
  }
}

describe('AudioRecorder', () => {
  const stopTrack = vi.fn()
  const getUserMedia = vi.fn()

  beforeEach(() => {
    vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:fake-url'),
      revokeObjectURL: vi.fn(),
    })

    getUserMedia.mockReset().mockResolvedValue({
      getTracks: () => [{ stop: stopTrack }],
    })
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia },
    })
  })

  it('mostra aviso quando o navegador não suporta gravação (contexto seguro)', () => {
    vi.stubGlobal('MediaRecorder', undefined)
    Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true })
    render(<AudioRecorder onRecorded={vi.fn()} />)

    expect(screen.getByText(/não é suportada neste navegador/i)).toBeInTheDocument()
  })

  it('mostra aviso de HTTPS quando o contexto não é seguro', () => {
    vi.stubGlobal('MediaRecorder', undefined)
    Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true })
    render(<AudioRecorder onRecorded={vi.fn()} />)

    expect(screen.getByText(/exige conexão segura/i)).toBeInTheDocument()
  })

  it('grava, mostra preview e confirma o áudio gravado', async () => {
    const onRecorded = vi.fn()
    render(<AudioRecorder onRecorded={onRecorded} />)

    fireEvent.click(screen.getByRole('button', { name: /iniciar gravação/i }))
    expect(await screen.findByText(/gravando/i)).toBeInTheDocument()
    expect(getUserMedia).toHaveBeenCalledWith({ audio: true })

    fireEvent.click(screen.getByRole('button', { name: /parar gravação/i }))

    const audio = await screen.findByTestId('recording-preview')
    expect(audio).toHaveAttribute('src', 'blob:fake-url')

    fireEvent.click(screen.getByRole('button', { name: /usar esta gravação/i }))

    expect(onRecorded).toHaveBeenCalledTimes(1)
    const file = onRecorded.mock.calls[0][0] as File
    expect(file).toBeInstanceOf(File)
    expect(file.name).toBe('gravacao.webm')
  })

  it('descarta a gravação e volta ao estado inicial', async () => {
    render(<AudioRecorder onRecorded={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: /iniciar gravação/i }))
    fireEvent.click(await screen.findByRole('button', { name: /parar gravação/i }))
    await screen.findByTestId('recording-preview')

    fireEvent.click(screen.getByRole('button', { name: /descartar/i }))

    expect(screen.getByRole('button', { name: /iniciar gravação/i })).toBeInTheDocument()
  })

  it('mostra mensagem de erro quando a permissão de microfone é negada', async () => {
    getUserMedia.mockRejectedValueOnce(new Error('denied'))
    render(<AudioRecorder onRecorded={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: /iniciar gravação/i }))

    expect(await screen.findByText(/não foi possível acessar o microfone/i)).toBeInTheDocument()
  })
})
