interface StateTimelineProps {
  status: string
  scheduledDate?: string | null
  notifyTenant?: boolean
}

export function StateTimeline({ status, scheduledDate, notifyTenant }: StateTimelineProps) {
  // Mapeia o status do ticket para o passo atual (1 a 5)
  const getStepState = (step: number) => {
    switch (step) {
      case 1: // Coleta de Orçamentos
        if (status === 'open' || status === 'waiting_quotes') return 'active'
        return 'completed'
      case 2: // Aprovação do Anfitrião
        if (status === 'open' || status === 'waiting_quotes') return 'pending'
        if (status === 'awaiting_adm_approval') return 'active'
        return 'completed'
      case 3: // Agendamento Urgência × Agenda
        if (['open', 'waiting_quotes', 'awaiting_adm_approval'].includes(status)) return 'pending'
        if (status === 'scheduling' || status === 'proposing_date') return 'active'
        return 'completed'
      case 4: // Confirmação do Prestador
        if (['open', 'waiting_quotes', 'awaiting_adm_approval', 'scheduling', 'proposing_date'].includes(status))
          return 'pending'
        if (status === 'waiting_date_confirmation') return 'active'
        return 'completed'
      case 5: // Notificação e Conclusão
        if (status === 'resolved' || status === 'confirmed_schedule') return 'completed'
        return 'pending'
      default:
        return 'pending'
    }
  }

  const steps = [
    {
      num: 1,
      title: '1. Coleta de Orçamentos',
      desc: 'Nó 3 solicita cotações aos prestadores homologados na região.',
    },
    {
      num: 2,
      title: '2. Decisão do Anfitrião',
      desc: 'Apresentação da síntese comparativa para aprovação humana (interrupt).',
    },
    {
      num: 3,
      title: '3. Regra Urgência × Agenda',
      desc: 'Cálculo determinístico da janela de atendimento sem conflito de hóspedes.',
    },
    {
      num: 4,
      title: '4. Confirmação do Prestador',
      desc: 'Validação da data com o profissional (loop de nova data em caso de recusa).',
    },
    {
      num: 5,
      title: '5. Aviso ao Hóspede e Conclusão',
      desc: notifyTenant
        ? 'Inquilino hospedado avisado via chat com detalhes da visita. Chamado RESOLVED.'
        : 'Chamado finalizado e visita registrada na agenda do imóvel. Chamado RESOLVED.',
    },
  ]

  return (
    <div className="timeline-card" aria-label="Progresso da resolução do chamado">
      <div>
        <h3 style={{ margin: 0 }}>Ciclo do Chamado (Fluxo C)</h3>
      </div>

      <div className="step-list">
        {steps.map((st) => {
          const state = getStepState(st.num)
          return (
            <div key={st.num} className={`step-item ${state}`}>
              <div className="step-number tabular-nums" aria-hidden="true">
                {state === 'completed' ? (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  st.num
                )}
              </div>
              <div className="step-content">
                <strong>{st.title}</strong>
                <span>{st.desc}</span>
              </div>
            </div>
          )
        })}
      </div>

      {scheduledDate && (
        <div
          style={{
            padding: '12px 14px',
            background: 'var(--mar-08)',
            borderRadius: '12px',
            fontSize: '13px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--ambar)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          <span>
            Agendado para: <strong>{scheduledDate}</strong>
          </span>
        </div>
      )}
    </div>
  )
}
