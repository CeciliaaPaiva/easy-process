import Link from 'next/link'

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gray-50 p-8">
      <div className="text-center">
        <h1 className="text-5xl font-bold tracking-tight text-gray-900">Easy Process</h1>
        <p className="mt-4 text-xl text-gray-500">
          Transforme entrevistas em áudio em diagramas BPMN com IA
        </p>
        <div className="mt-8 flex justify-center gap-4">
          <Link
            href="/login"
            className="rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white transition-colors hover:bg-blue-700"
          >
            Entrar
          </Link>
        </div>
      </div>
    </main>
  )
}
