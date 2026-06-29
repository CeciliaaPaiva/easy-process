'use client'

import { useEffect } from 'react'

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-gray-50 text-center">
      <h1 className="text-6xl font-bold text-gray-200">500</h1>
      <h2 className="text-xl font-semibold text-gray-700">Algo deu errado</h2>
      <p className="text-sm text-gray-500">Ocorreu um erro inesperado. Tente novamente.</p>
      <button
        onClick={reset}
        className="mt-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
      >
        Tentar novamente
      </button>
    </div>
  )
}
