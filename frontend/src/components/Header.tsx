import { useEffect, useState } from 'react'
import { fetchCostSummary } from '../api/client'
import type { CostSummary } from '../contracts'

const usd = (val: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(val)

export function ZeloLogo({ size = 38 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 72 72" role="img" aria-label="Símbolo Zelo">
      <rect width="72" height="72" rx="20" fill="#17323A" />
      <path
        d="M18 36 L36 21 L54 36"
        fill="none"
        stroke="#F6F3EE"
        strokeWidth="5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M25 33 V51 H47 V33"
        fill="none"
        stroke="#F6F3EE"
        strokeWidth="5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="36" cy="41.5" r="5" fill="#F2A541" />
    </svg>
  )
}

export function Header({
  navigate,
  activeView = 'imoveis',
}: {
  navigate: (url: string) => void
  activeView?: 'imoveis' | 'auditoria'
}) {
  const [costs, setCosts] = useState<CostSummary | null>(null)

  useEffect(() => {
    fetchCostSummary().then(setCosts).catch(() => {})
    const interval = setInterval(() => {
      fetchCostSummary().then(setCosts).catch(() => {})
    }, 10000)
    return () => clearInterval(interval)
  }, [])

  const spent = costs?.total_cost_usd ?? 0.002
  const limit = costs?.budget_limit_usd ?? 25.0
  const percent = Math.min(100, (spent / limit) * 100)
  const isAlert = percent >= 75

  return (
    <header className="site-header">
      <div className="page-width header-inner">
        <a
          href="/"
          className="brand"
          onClick={(e) => {
            e.preventDefault()
            navigate('/')
          }}
          aria-label="Zelo, ir para início"
        >
          <div className="brand-symbol" aria-hidden="true">
            <ZeloLogo size={40} />
          </div>
          <div className="brand-copy">
            <span>zelo</span>
            <small>Quebrou algo no imóvel? A gente resolve. Você só aprova.</small>
          </div>
        </a>

        <nav className="header-nav" aria-label="Navegação principal">
          <a
            href="/"
            className={activeView === 'imoveis' ? 'active' : ''}
            onClick={(e) => {
              e.preventDefault()
              navigate('/')
            }}
          >
            Explorar imóveis
          </a>
          <span className="nav-divider" />
          <a
            href="/auditoria"
            className={activeView === 'auditoria' ? 'active' : ''}
            onClick={(e) => {
              e.preventDefault()
              navigate('/auditoria')
            }}
          >
            Painel do anfitrião & Custos
          </a>
        </nav>

        <div
          className={`budget-monitor ${isAlert ? 'alert' : ''}`}
          title={`Orçamento de IA: ${usd(spent)} de ${usd(limit)} (${percent.toFixed(1)}%)`}
          aria-label={`Orçamento IA: ${usd(spent)} de ${usd(limit)}`}
        >
          <div className={`budget-dot ${isAlert ? 'alert' : ''}`} aria-hidden="true" />
          <div className="budget-info">
            <strong>Orçamento IA</strong>
            <span className="tabular-nums">
              {usd(spent)} / {usd(limit)}
            </span>
          </div>
          <div
            className="budget-bar"
            role="progressbar"
            aria-valuenow={spent}
            aria-valuemin={0}
            aria-valuemax={limit}
            aria-label="Consumo do orçamento"
          >
            <div
              className={`budget-bar-fill ${isAlert ? 'alert' : ''}`}
              style={{ width: `${Math.max(4, percent)}%` }}
            />
          </div>
        </div>
      </div>
    </header>
  )
}
