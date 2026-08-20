interface IconProps {
  size?: number;
  danger?: boolean;
}

// Stessa direzione/tonalità di gradiente delle grafiche di riferimento fornite
// dall'utente: viola intenso in basso a sinistra, magenta chiaro in alto a destra.
const GRADIENTS = {
  brand: { from: "#9333ea", to: "#f0abfc" },
  danger: { from: "#a21caf", to: "#f0abfc" },
};

function GlossyCircle({
  id,
  danger,
  children,
}: {
  id: string;
  danger?: boolean;
  children: React.ReactNode;
}) {
  const g = danger ? GRADIENTS.danger : GRADIENTS.brand;
  return (
    <>
      <defs>
        <linearGradient id={`${id}-fill`} x1="6" y1="42" x2="42" y2="6" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor={g.from} />
          <stop offset="100%" stopColor={g.to} />
        </linearGradient>
        <radialGradient id={`${id}-sheen`} cx="34%" cy="26%" r="60%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.5" />
          <stop offset="55%" stopColor="#ffffff" stopOpacity="0.06" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`${id}-glyph`} x1="16" y1="10" x2="34" y2="38" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#fbe8ff" />
        </linearGradient>
      </defs>
      <circle cx="24" cy="24" r="24" fill={`url(#${id}-fill)`} />
      <circle cx="24" cy="24" r="24" fill={`url(#${id}-sheen)`} />
      {children}
    </>
  );
}

export function SendIcon({ size = 44, danger = false }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <GlossyCircle id="send" danger={danger}>
        {/* corpo principale della carta, punta verso l'alto a destra */}
        <path d="M11 23L36 10L25 37L21.5 26.5L11 23Z" fill="url(#send-glyph)" stroke="#ffffff" strokeOpacity="0.4" strokeWidth="0.4" strokeLinejoin="round" />
        {/* piega inferiore, ombra leggermente più scura */}
        <path d="M21.5 26.5L25 37L18 30.5L21.5 26.5Z" fill="#ffffff" fillOpacity="0.55" />
        {/* piega destra verso la punta, sfaccettatura più scura */}
        <path d="M21.5 26.5L36 10L28.5 24L21.5 26.5Z" fill="#e9b8fb" fillOpacity="0.55" />
        {/* riflesso lucido lungo la costa superiore */}
        <path d="M13 22.3L35 11.2L23.5 25L13 22.3Z" fill="#ffffff" fillOpacity="0.35" />
      </GlossyCircle>
    </svg>
  );
}

export function MicIcon({ size = 44, danger = false }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <GlossyCircle id="mic" danger={danger}>
        <rect x="18" y="8" width="12" height="20" rx="6" fill="url(#mic-glyph)" />
        <rect x="18" y="8" width="6" height="20" rx="3" fill="#ffffff" fillOpacity="0.5" />
        <path
          d="M13 21v2a11 11 0 0 0 22 0v-2"
          fill="none"
          stroke="#ffffff"
          strokeOpacity="0.92"
          strokeWidth="2.6"
          strokeLinecap="round"
        />
        <line x1="24" y1="34" x2="24" y2="39.5" stroke="#ffffff" strokeOpacity="0.92" strokeWidth="2.6" strokeLinecap="round" />
        <line x1="17.5" y1="39.5" x2="30.5" y2="39.5" stroke="#ffffff" strokeOpacity="0.92" strokeWidth="2.6" strokeLinecap="round" />
      </GlossyCircle>
    </svg>
  );
}

export function StopIcon({ size = 44, danger = true }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <GlossyCircle id="stop" danger={danger}>
        <rect x="17" y="17" width="14" height="14" rx="3" fill="url(#stop-glyph)" />
      </GlossyCircle>
    </svg>
  );
}
