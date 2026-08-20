interface IconProps {
  size?: number;
  danger?: boolean;
}

const GRADIENTS = {
  brand: { from: "#a78bfa", to: "#f472b6" },
  danger: { from: "#f0abfc", to: "#e881f8" },
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
        <linearGradient id={`${id}-fill`} x1="4" y1="2" x2="44" y2="46" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor={g.from} />
          <stop offset="100%" stopColor={g.to} />
        </linearGradient>
        <radialGradient id={`${id}-sheen`} cx="32%" cy="24%" r="65%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.55" />
          <stop offset="55%" stopColor="#ffffff" stopOpacity="0.08" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
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
        <path
          d="M14 24L34 13L27 34L23.5 25.5L14 24Z"
          fill="#ffffff"
          fillOpacity="0.96"
          stroke="#ffffff"
          strokeOpacity="0.3"
          strokeWidth="0.5"
          strokeLinejoin="round"
        />
        <path d="M23.5 25.5L34 13L18.5 21.5L23.5 25.5Z" fill="#ffffff" fillOpacity="0.45" />
      </GlossyCircle>
    </svg>
  );
}

export function MicIcon({ size = 44, danger = false }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <GlossyCircle id="mic" danger={danger}>
        <rect x="19" y="10" width="10" height="16" rx="5" fill="#ffffff" fillOpacity="0.96" />
        <path
          d="M14 21v2a10 10 0 0 0 20 0v-2"
          fill="none"
          stroke="#ffffff"
          strokeOpacity="0.9"
          strokeWidth="2.4"
          strokeLinecap="round"
        />
        <line x1="24" y1="33" x2="24" y2="38" stroke="#ffffff" strokeOpacity="0.9" strokeWidth="2.4" strokeLinecap="round" />
        <line x1="18" y1="38" x2="30" y2="38" stroke="#ffffff" strokeOpacity="0.9" strokeWidth="2.4" strokeLinecap="round" />
      </GlossyCircle>
    </svg>
  );
}

export function StopIcon({ size = 44, danger = true }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <GlossyCircle id="stop" danger={danger}>
        <rect x="17" y="17" width="14" height="14" rx="3" fill="#ffffff" fillOpacity="0.96" />
      </GlossyCircle>
    </svg>
  );
}
