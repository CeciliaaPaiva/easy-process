import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-gray-50 text-center">
      <h1 className="text-6xl font-bold text-gray-200">404</h1>
      <h2 className="text-xl font-semibold text-gray-700">Página não encontrada</h2>
      <p className="text-sm text-gray-500">O recurso que você procura não existe ou foi removido.</p>
      <Link
        href="/projects"
        className="mt-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
      >
        Ir para projetos
      </Link>
    </div>
  )
}
