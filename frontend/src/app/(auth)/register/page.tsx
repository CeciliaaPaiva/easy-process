'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { FormEvent, useState } from 'react'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import { setTokens } from '@/lib/auth'
import type { AuthResponse } from '@/types'

export default function RegisterPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError('')
    setLoading(true)

    const form = e.currentTarget
    const name = (form.elements.namedItem('name') as HTMLInputElement).value
    const email = (form.elements.namedItem('email') as HTMLInputElement).value
    const password = (form.elements.namedItem('password') as HTMLInputElement).value
    const company_name = (form.elements.namedItem('company_name') as HTMLInputElement).value

    try {
      const data = await api.post<AuthResponse>('/api/v1/auth/register', {
        name,
        email,
        password,
        company_name,
      })
      setTokens(data.access_token, data.refresh_token)
      router.push('/projects')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar conta')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-md rounded-xl bg-white p-8 shadow-sm ring-1 ring-gray-200">
      <h2 className="text-xl font-semibold text-gray-900">Criar conta</h2>
      <p className="mt-1 text-sm text-gray-500">
        Já tem conta?{' '}
        <Link href="/login" className="text-blue-600 hover:underline">
          Entrar
        </Link>
      </p>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        {error && <Alert message={error} />}

        <Input
          id="name"
          name="name"
          type="text"
          label="Seu nome"
          placeholder="João Silva"
          autoComplete="name"
          required
          minLength={2}
        />
        <Input
          id="company_name"
          name="company_name"
          type="text"
          label="Nome da empresa"
          placeholder="Minha Empresa Ltda"
          required
          minLength={2}
        />
        <Input
          id="email"
          name="email"
          type="email"
          label="E-mail corporativo"
          placeholder="joao@empresa.com"
          autoComplete="email"
          required
        />
        <Input
          id="password"
          name="password"
          type="password"
          label="Senha"
          placeholder="Mínimo 6 caracteres"
          autoComplete="new-password"
          required
          minLength={6}
        />

        <Button type="submit" loading={loading} className="mt-2 w-full">
          Criar conta grátis
        </Button>

        <p className="text-center text-xs text-gray-400">
          Ao criar sua conta você concorda com os termos de uso.
        </p>
      </form>
    </div>
  )
}
