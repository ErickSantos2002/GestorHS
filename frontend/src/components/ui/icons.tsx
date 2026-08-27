interface IconProps {
  className?: string
}

function base(className?: string) {
  return className ?? 'w-5 h-5 shrink-0'
}

export function IconMenu({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  )
}

export function IconSun({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2m0 14v2m9-9h-2M5 12H3m15.36 6.36-1.42-1.42M6.34 6.34 4.93 4.93m12.73 0-1.42 1.42M6.34 17.66l-1.41 1.41M12 8a4 4 0 100 8 4 4 0 000-8z" />
    </svg>
  )
}

export function IconMoon({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
    </svg>
  )
}

export function IconLogout({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H9m4 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
    </svg>
  )
}

export function IconDashboard({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l9-9 9 9M5 10v10a1 1 0 001 1h3v-6h6v6h3a1 1 0 001-1V10" />
    </svg>
  )
}

export function IconChevronDown({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 9l6 6 6-6" />
    </svg>
  )
}

export function IconAlertCircle({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}

export function IconX({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

export function IconUsers({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m3.5-2.13a4 4 0 10-3-7.74 4 4 0 003 7.74zm6 0a4 4 0 10-3-7.74" />
    </svg>
  )
}

export function IconUser({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 12a4 4 0 100-8 4 4 0 000 8zm-7 8a7 7 0 0114 0" />
    </svg>
  )
}

export function IconCadastros({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h9l5 5v9a2 2 0 01-2 2H6a2 2 0 01-2-2V6z M8 10h8 M8 14h5" />
    </svg>
  )
}

export function IconClientes({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m3.5-2.13a4 4 0 10-3-7.74 4 4 0 003 7.74zm6 0a4 4 0 10-3-7.74" />
    </svg>
  )
}

export function IconFrota({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 7h11v8H4z M15 10h4l2 3v2h-6z M7.5 18a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z M18.5 18a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z" />
    </svg>
  )
}

export function IconOrdens({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
    </svg>
  )
}

export function IconCobranca({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.4-1.4A2 2 0 0118 14.2V11a6 6 0 00-4-5.66V5a2 2 0 10-4 0v.34A6 6 0 006 11v3.2a2 2 0 01-.6 1.4L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
    </svg>
  )
}

export function IconSolicitacoes({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h8M8 14h5m-5 7l-4-4h12a3 3 0 003-3V7a3 3 0 00-3-3H6a3 3 0 00-3 3v14z" />
    </svg>
  )
}

export function IconCaixas({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 8 12 3 3 8l9 5 9-5Z" />
      <path d="M3 8v8l9 5 9-5V8" />
      <path d="M12 13v8" />
    </svg>
  )
}

export function IconCalendar({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 9h18M8 3v4M16 3v4" />
    </svg>
  )
}

export function IconWrench({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.7 6.3a4 4 0 0 0-5.3 5l-6 6a1.5 1.5 0 0 0 2.1 2.1l6-6a4 4 0 0 0 5-5.3l-2.4 2.4-2.1-.6-.6-2.1 2.4-2.4Z" />
    </svg>
  )
}

export function IconTag({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7v5l9 9 7-7-9-9H3Z" />
      <circle cx="7.5" cy="7.5" r="1.25" />
    </svg>
  )
}

export function IconBattery({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="8" width="16" height="8" rx="2" />
      <path d="M22 11v2" />
    </svg>
  )
}

export function IconSearch({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  )
}

export function IconPlus({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 5v14M5 12h14" />
    </svg>
  )
}

export function IconNote({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v9l-5 5H6a2 2 0 0 1-2-2V5Z" />
      <path d="M14 19v-3a1 1 0 0 1 1-1h3M8 8h8M8 12h5" />
    </svg>
  )
}

export function IconChevronLeft({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 18l-6-6 6-6" />
    </svg>
  )
}

export function IconChevronRight({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 6l6 6-6 6" />
    </svg>
  )
}

export function IconClock({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  )
}

export function IconCamera({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8a2 2 0 0 1 2-2h2l1.5-2h7L19 6h0a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8Z" />
      <circle cx="12" cy="13" r="3.5" />
    </svg>
  )
}

export function IconCheck({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 13l4 4L19 7" />
    </svg>
  )
}

export function IconChart({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19V5M4 19h16M8 16v-5M12 16V8M16 16v-3" />
    </svg>
  )
}

export function IconPencil({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5Z" />
      <path d="m14.5 5.5 4 4" />
    </svg>
  )
}

export function IconTrash({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
      <path d="M6 7v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7M10 11v6M14 11v6" />
    </svg>
  )
}

/** Círculo cortado: desabilitar (tirar de circulação sem apagar). */
export function IconBan({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="m5.6 5.6 12.8 12.8" />
    </svg>
  )
}

/** Seta voltando sobre um arco: reativar o que foi desabilitado. */
export function IconRestore({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <path d="M3 4v5h5" />
    </svg>
  )
}

export function IconEye({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

export function IconKey({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="15" r="4" />
      <path d="m10.85 12.15 8.15-8.15M17 6l2 2M14 9l2 2" />
    </svg>
  )
}

export function IconUserOff({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8a7 7 0 0 1 11.3-5.5" />
      <path d="M16 18h6" />
    </svg>
  )
}

export function IconUserCheck({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8a7 7 0 0 1 11.3-5.5" />
      <path d="m16 17.5 2 2 4-4" />
    </svg>
  )
}

export function IconPhone({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 5a2 2 0 0 1 2-2h1.6a1 1 0 0 1 1 .76l.9 3.6a1 1 0 0 1-.53 1.13L7.6 9.4a12 12 0 0 0 5 5l.9-1.37a1 1 0 0 1 1.14-.53l3.6.9a1 1 0 0 1 .76 1V16a2 2 0 0 1-2 2h-.5A13.5 13.5 0 0 1 4 5.5V5Z" />
    </svg>
  )
}

export function IconDownload({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v12m0 0 4-4m-4 4-4-4" />
      <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
    </svg>
  )
}

export function IconCopy({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="9" width="12" height="12" rx="2" />
      <path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" />
    </svg>
  )
}

export function IconCertificado({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 3h9l4 4v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
      <path d="M14 3v4h4M8 17l-1.5 3 2-1 2 1L13 17" />
      <circle cx="10.5" cy="12" r="2.5" />
    </svg>
  )
}
