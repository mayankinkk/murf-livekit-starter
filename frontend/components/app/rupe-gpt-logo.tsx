import { cn } from '@/lib/shadcn/utils';

type RupeeLogoProps = React.SVGProps<SVGSVGElement>;

/**
 * RupeeGPT brand mark — a premium geometric logo integrating the Indian Rupee
 * symbol (₹) with voice/audio frequency wave bars.
 */
export function RupeeLogo({ className, ...props }: RupeeLogoProps) {
  return (
    <svg
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('size-12', className)}
      aria-hidden="true"
      {...props}
    >
      <defs>
        <linearGradient id="rupee-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#C4A7FF" />
          <stop offset="50%" stopColor="#8B5CF6" />
          <stop offset="100%" stopColor="#6D3FD9" />
        </linearGradient>
        <linearGradient id="wave-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#F0C8FF" />
          <stop offset="100%" stopColor="#8B5CF6" />
        </linearGradient>
      </defs>
      {/* Outer subtle glowing ring */}
      <circle
        cx="50"
        cy="50"
        r="46"
        stroke="url(#rupee-grad)"
        strokeWidth="1.5"
        strokeOpacity="0.3"
        fill="rgba(18, 10, 46, 0.2)"
      />

      {/* Modern stylized Rupee path */}
      <path
        d="M38 32H62M38 42H58M38 32V60C38 60 48 60 52 50C56 40 64 68 64 68M52 42C56.5 42 60 38.5 60 35C60 31.5 56.5 32 52 32"
        stroke="url(#rupee-grad)"
        strokeWidth="6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Voice wave bars framing the rupee symbol */}
      {/* Left wave bars */}
      <rect x="22" y="42" width="3" height="16" rx="1.5" fill="url(#wave-grad)" opacity="0.6" />
      <rect x="16" y="46" width="3" height="8" rx="1.5" fill="url(#wave-grad)" opacity="0.4" />

      {/* Right wave bars */}
      <rect x="75" y="42" width="3" height="16" rx="1.5" fill="url(#wave-grad)" opacity="0.6" />
      <rect x="81" y="46" width="3" height="8" rx="1.5" fill="url(#wave-grad)" opacity="0.4" />
    </svg>
  );
}
