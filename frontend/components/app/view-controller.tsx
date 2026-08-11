'use client';

import { MicOff } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useSessionContext } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { AgentSessionView_01 } from '@/components/agents-ui/blocks/agent-session-view-01';
import { EndedView } from '@/components/app/ended-view';
import { WelcomeView } from '@/components/app/welcome-view';
import { Button } from '@/components/ui/button';
import { useVoiceAgentStatus } from '@/hooks/use-voice-agent-status';
import { cn } from '@/lib/shadcn/utils';

const MotionWelcomeView = motion.create(WelcomeView);
const MotionEndedView = motion.create(EndedView);
const MotionSessionView = motion.create(AgentSessionView_01);

const VIEW_MOTION_PROPS = {
  variants: {
    visible: {
      opacity: 1,
    },
    hidden: {
      opacity: 0,
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.5,
    ease: 'linear',
  },
};

const FALLING_RUPEES = [
  // ── Left side particles (8) ──
  {
    id: 1,
    left: '3%',
    duration: '12s',
    delay: '-0s',
    color: '#FFD34E',
    fontSize: '24px',
    textShadow: '0 0 8px rgba(255,211,78,0.45), 0 0 18px rgba(255,193,7,0.20)',
  },
  {
    id: 2,
    left: '8%',
    duration: '15s',
    delay: '-2s',
    color: '#F5C542',
    fontSize: '32px',
    textShadow: '0 0 10px rgba(245,197,66,0.50), 0 0 22px rgba(255,193,7,0.25)',
  },
  {
    id: 3,
    left: '12%',
    duration: '13s',
    delay: '-4s',
    color: '#FFC857',
    fontSize: '20px',
    textShadow: '0 0 6px rgba(255,200,87,0.40), 0 0 14px rgba(255,193,7,0.18)',
  },
  {
    id: 4,
    left: '5%',
    duration: '16s',
    delay: '-6s',
    color: '#FFD34E',
    fontSize: '28px',
    filter: 'blur(0.5px)',
    textShadow: '0 0 8px rgba(255,211,78,0.45), 0 0 18px rgba(255,193,7,0.20)',
  },
  {
    id: 5,
    left: '14%',
    duration: '11s',
    delay: '-8s',
    color: '#F5C542',
    fontSize: '22px',
    textShadow: '0 0 7px rgba(245,197,66,0.42), 0 0 16px rgba(255,193,7,0.20)',
  },
  {
    id: 6,
    left: '2%',
    duration: '14s',
    delay: '-10s',
    color: '#FFC857',
    fontSize: '26px',
    textShadow: '0 0 8px rgba(255,200,87,0.45), 0 0 18px rgba(255,193,7,0.22)',
  },
  {
    id: 7,
    left: '10%',
    duration: '17s',
    delay: '-12s',
    color: '#FFD34E',
    fontSize: '18px',
    filter: 'blur(1px)',
    textShadow: '0 0 6px rgba(255,211,78,0.35), 0 0 14px rgba(255,193,7,0.15)',
  },
  {
    id: 8,
    left: '6%',
    duration: '13s',
    delay: '-14s',
    color: '#F5C542',
    fontSize: '30px',
    textShadow: '0 0 10px rgba(245,197,66,0.48), 0 0 20px rgba(255,193,7,0.22)',
  },

  // ── Right side particles (8) ──
  {
    id: 9,
    right: '3%',
    duration: '13s',
    delay: '-1s',
    color: '#FFD34E',
    fontSize: '28px',
    textShadow: '0 0 8px rgba(255,211,78,0.45), 0 0 18px rgba(255,193,7,0.20)',
  },
  {
    id: 10,
    right: '9%',
    duration: '15s',
    delay: '-3s',
    color: '#FFC857',
    fontSize: '24px',
    textShadow: '0 0 8px rgba(255,200,87,0.45), 0 0 18px rgba(255,193,7,0.22)',
  },
  {
    id: 11,
    right: '13%',
    duration: '12s',
    delay: '-5s',
    color: '#F5C542',
    fontSize: '32px',
    textShadow: '0 0 10px rgba(245,197,66,0.50), 0 0 22px rgba(255,193,7,0.25)',
  },
  {
    id: 12,
    right: '6%',
    duration: '16s',
    delay: '-7s',
    color: '#FFD34E',
    fontSize: '20px',
    filter: 'blur(0.5px)',
    textShadow: '0 0 6px rgba(255,211,78,0.40), 0 0 14px rgba(255,193,7,0.18)',
  },
  {
    id: 13,
    right: '14%',
    duration: '11s',
    delay: '-9s',
    color: '#FFC857',
    fontSize: '26px',
    textShadow: '0 0 8px rgba(255,200,87,0.45), 0 0 18px rgba(255,193,7,0.22)',
  },
  {
    id: 14,
    right: '4%',
    duration: '14s',
    delay: '-11s',
    color: '#F5C542',
    fontSize: '22px',
    textShadow: '0 0 7px rgba(245,197,66,0.42), 0 0 16px rgba(255,193,7,0.20)',
  },
  {
    id: 15,
    right: '11%',
    duration: '17s',
    delay: '-13s',
    color: '#FFD34E',
    fontSize: '18px',
    filter: 'blur(1px)',
    textShadow: '0 0 6px rgba(255,211,78,0.35), 0 0 14px rgba(255,193,7,0.15)',
  },
  {
    id: 16,
    right: '7%',
    duration: '13s',
    delay: '-15s',
    color: '#F5C542',
    fontSize: '30px',
    textShadow: '0 0 10px rgba(245,197,66,0.48), 0 0 20px rgba(255,193,7,0.22)',
  },
];

interface ViewControllerProps {
  appConfig: AppConfig;
}

export function ViewController({ appConfig }: ViewControllerProps) {
  const { isConnected, start } = useSessionContext();
  const { status, micPermissionDenied, clearMicPermissionError, retryStart } =
    useVoiceAgentStatus();

  // The welcome page stays fully separate: the session UI (with the glowing
  // orb) only mounts once START is pressed. The real LiveKit "connecting"
  // state is therefore shown between pressing START and `isConnected`.
  const isEnded = !isConnected && status === 'ended';

  return (
    <div className="relative h-full w-full overflow-hidden bg-[#050505]">
      {/* Gold falling rupees */}
      <div className="pointer-events-none absolute inset-0 z-40 overflow-hidden">
        {FALLING_RUPEES.map((p, idx) => {
          // Show 6 particles on mobile (3 left + 3 right), all 16 on desktop
          const MOBILE_VISIBLE_IDS = [1, 2, 5, 9, 10, 13];
          const isMobileHidden = !MOBILE_VISIBLE_IDS.includes(p.id);
          return (
            <span
              key={p.id}
              className={cn(
                'falling-rupee absolute font-serif select-none',
                isMobileHidden && 'hidden md:block'
              )}
              style={
                {
                  left: p.left,
                  right: p.right,
                  fontSize: p.fontSize,
                  filter: p.filter,
                  textShadow: p.textShadow,
                  color: p.color,
                  animationDelay: p.delay,
                  animationDuration: p.duration,
                } as React.CSSProperties
              }
            >
              ₹
            </span>
          );
        })}
      </div>

      {/* Persistent Brand Logo Top-Left */}
      <div className="pointer-events-none absolute top-4 left-6 z-50 select-none md:top-6 md:left-8">
        <img
          src="/rupegpt-logo.png"
          alt="RupeeGPT Logo"
          className="h-auto w-[200px] object-contain md:w-[280px]"
        />
      </div>

      <AnimatePresence mode="wait">
        {/* Microphone permission error fullscreen state */}
        {micPermissionDenied ? (
          <motion.div
            key="mic-error"
            {...VIEW_MOTION_PROPS}
            className="flex h-full w-full flex-col items-center justify-center gap-10 bg-[#050505] px-6 py-14 text-center"
          >
            <div className="flex w-full max-w-md flex-col items-center gap-4 rounded-3xl border border-red-500/20 bg-[#0b0b0b]/90 p-8 shadow-[0_8px_30px_rgba(0,0,0,0.6)] backdrop-blur-md md:p-10">
              <span className="mb-2 flex size-16 items-center justify-center rounded-full border border-red-500/30 bg-red-950/20 text-red-500 shadow-[0_0_20px_rgba(239,68,68,0.15)]">
                <MicOff className="size-7 animate-pulse" />
              </span>
              <h2 className="text-2xl font-semibold tracking-wide text-[#f5f5f5]">
                Microphone access is required
              </h2>
              <p className="max-w-xs text-sm leading-relaxed text-[#9a9a9a]">
                Allow microphone access in your browser settings, then try again.
              </p>
              <div className="mt-6 flex w-full flex-col gap-3 sm:flex-row">
                <Button
                  onClick={retryStart}
                  className="flex-1 cursor-pointer rounded-full bg-[#6d3fd9] py-6 font-sans text-sm font-semibold tracking-wider text-white shadow-[0_0_20px_rgba(109,63,217,0.3)] transition-all duration-300 hover:bg-[#8b5cf6]"
                >
                  TRY AGAIN
                </Button>
                <Button
                  variant="outline"
                  onClick={clearMicPermissionError}
                  className="flex-1 cursor-pointer rounded-full border-white/[0.08] bg-white/[0.02] py-6 font-sans text-sm font-semibold tracking-wider text-[#9a9a9a] hover:bg-white/[0.05] hover:text-[#f5f5f5]"
                >
                  DISMISS
                </Button>
              </div>
            </div>
          </motion.div>
        ) : (
          <>
            {/* Welcome view — shown before the first call, no orb */}
            {status === 'ready' && (
              <MotionWelcomeView
                key="welcome"
                {...VIEW_MOTION_PROPS}
                title={appConfig.welcomeTitle}
                subtitle={appConfig.welcomeSubtitle}
                description={appConfig.welcomeDescription}
                startButtonText={appConfig.startButtonText}
                onStartCall={start}
              />
            )}
            {/* Ended view — a previous call finished, offer to start again */}
            {isEnded && <MotionEndedView key="ended" {...VIEW_MOTION_PROPS} onStartAgain={start} />}
            {/* Session view — connecting (START pressed, not yet connected) or connected */}
            {(status === 'connecting' || isConnected) && (
              <MotionSessionView
                key="session-view"
                {...VIEW_MOTION_PROPS}
                aiLoaderStatus={status}
                supportsChatInput={appConfig.supportsChatInput}
                supportsVideoInput={appConfig.supportsVideoInput}
                supportsScreenShare={appConfig.supportsScreenShare}
                isPreConnectBufferEnabled={appConfig.isPreConnectBufferEnabled}
                className="fixed inset-0"
              />
            )}
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
