export default function LuceMark({ size = 22, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      className={`luce-mark ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="luceMarkGradient" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#a78bfa" />
          <stop offset="100%" stopColor="#f472b6" />
        </linearGradient>
      </defs>
      <path
        d="M12 0C12 6 6 12 0 12C6 12 12 18 12 24C12 18 18 12 24 12C18 12 12 6 12 0Z"
        fill="url(#luceMarkGradient)"
      />
    </svg>
  );
}
