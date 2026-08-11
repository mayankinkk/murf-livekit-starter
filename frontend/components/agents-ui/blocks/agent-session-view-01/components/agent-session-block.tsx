'use client';

import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, type MotionProps, motion } from 'motion/react';
import { useAgent, useSessionContext, useSessionMessages } from '@livekit/components-react';
import { AgentChatTranscript } from '@/components/agents-ui/agent-chat-transcript';
import {
  AgentControlBar,
  type AgentControlBarControls,
} from '@/components/agents-ui/agent-control-bar';
import { Shimmer } from '@/components/ai-elements/shimmer';
import type { AiLoaderStatus } from '@/components/ui/ai-loader';
import { VoiceBarVisualizer } from '@/components/ui/voice-bar-visualizer';
import { cn } from '@/lib/shadcn/utils';

const MotionMessage = motion.create(Shimmer);

const BOTTOM_VIEW_MOTION_PROPS: MotionProps = {
  variants: {
    visible: {
      opacity: 1,
      translateY: '0%',
    },
    hidden: {
      opacity: 0,
      translateY: '100%',
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.3,
    delay: 0.5,
    ease: 'easeOut',
  },
};

const CHAT_MOTION_PROPS: MotionProps = {
  variants: {
    hidden: {
      opacity: 0,
      transition: {
        ease: 'easeOut',
        duration: 0.3,
      },
    },
    visible: {
      opacity: 1,
      transition: {
        delay: 0.2,
        ease: 'easeOut',
        duration: 0.3,
      },
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
};

const SHIMMER_MOTION_PROPS: MotionProps = {
  variants: {
    visible: {
      opacity: 1,
      transition: {
        ease: 'easeIn',
        duration: 0.5,
        delay: 0.8,
      },
    },
    hidden: {
      opacity: 0,
      transition: {
        ease: 'easeIn',
        duration: 0.5,
        delay: 0,
      },
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
};

interface FadeProps {
  top?: boolean;
  bottom?: boolean;
  className?: string;
}

export function Fade({ top = false, bottom = false, className }: FadeProps) {
  return (
    <div
      className={cn(
        'pointer-events-none h-4 bg-linear-to-b from-[#050505] to-transparent',
        top && 'bg-linear-to-b',
        bottom && 'bg-linear-to-t',
        className
      )}
    />
  );
}

export interface AgentSessionView_01Props {
  /**
   * Message shown above the controls before the first chat message is sent.
   *
   * @default 'Agent is listening, ask it a question'
   */
  preConnectMessage?: string;
  /**
   * Enables or disables the chat toggle and transcript input controls.
   *
   * @default true
   */
  supportsChatInput?: boolean;
  /**
   * Enables or disables camera controls in the bottom control bar.
   *
   * @default true
   */
  supportsVideoInput?: boolean;
  /**
   * Enables or disables screen sharing controls in the bottom control bar.
   *
   * @default true
   */
  supportsScreenShare?: boolean;
  /**
   * Shows a pre-connect buffer state with a shimmer message before messages appear.
   *
   * @default true
   */
  isPreConnectBufferEnabled?: boolean;

  /**
   * Live RupeeGPT Voice agent state used to drive the status pill and the
   * glowing orb at the center of the connected session.
   *
   * @default 'connecting'
   */
  aiLoaderStatus?: AiLoaderStatus;
  /** Optional class name merged onto the outer `<section>` container. */
  className?: string;
}

export function AgentSessionView_01({
  preConnectMessage = 'Agent is listening, ask it a question',
  supportsChatInput = true,
  supportsVideoInput = true,
  supportsScreenShare = true,
  isPreConnectBufferEnabled = true,

  aiLoaderStatus = 'connecting',
  className,
  ...props
}: React.ComponentProps<'section'> & AgentSessionView_01Props) {
  const session = useSessionContext();
  const { messages } = useSessionMessages(session);
  const [chatOpen, setChatOpen] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const { state: agentState } = useAgent();

  const controls: AgentControlBarControls = {
    leave: true,
    microphone: true,
    chat: supportsChatInput,
    camera: supportsVideoInput,
    screenShare: supportsScreenShare,
  };

  useEffect(() => {
    const lastMessage = messages.at(-1);
    const lastMessageIsLocal = lastMessage?.from?.isLocal === true;

    if (scrollAreaRef.current && lastMessageIsLocal) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <section
      className={cn('relative z-10 h-full w-full overflow-hidden bg-[#050505]', className)}
      {...props}
    >
      <Fade top className="absolute inset-x-4 top-0 z-10 h-40" />

      {/* Live voice agent status pill */}
      <div className="pointer-events-none absolute inset-x-0 top-6 z-30 flex justify-center px-4">
        <div className="flex items-center gap-2 rounded-full border border-white/[0.08] bg-[#0b0b0b]/90 px-4.5 py-1.5 shadow-[0_4px_20px_rgba(0,0,0,0.4)] backdrop-blur-md">
          <span
            className={cn(
              'mr-1 size-1.5 animate-pulse rounded-full',
              aiLoaderStatus === 'speaking' && 'bg-[#8b5cf6] shadow-[0_0_6px_#8b5cf6]',
              aiLoaderStatus === 'listening' && 'bg-[#c4a7ff] shadow-[0_0_6px_#c4a7ff]',
              aiLoaderStatus === 'connecting' &&
                'bg-amber-500 shadow-[0_0_6px_rgba(245,158,11,0.5)]'
            )}
          />
          <span className="font-sans text-[9px] font-semibold tracking-[0.25em] text-[#f5f5f5] uppercase">
            {aiLoaderStatus === 'speaking'
              ? 'SPEAKING...'
              : aiLoaderStatus === 'listening'
                ? 'LISTENING TO YOU...'
                : 'CONNECTING...'}
          </span>
        </div>
      </div>

      {/* Transcript view when chat toggle is open */}
      <div className="absolute top-0 bottom-[135px] flex w-full flex-col md:bottom-[170px]">
        <AnimatePresence>
          {chatOpen && (
            <motion.div
              {...CHAT_MOTION_PROPS}
              className="flex h-full w-full flex-col gap-4 space-y-3 transition-opacity duration-300 ease-out"
            >
              <AgentChatTranscript
                agentState={agentState}
                messages={messages}
                className="mx-auto w-full max-w-2xl [&_.is-user>div]:rounded-[22px] [&>div>div]:px-4 [&>div>div]:pt-40 md:[&>div>div]:px-6"
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Main AI Voice Bar Visualizer */}
      <div className="absolute inset-0 flex items-center justify-center pt-16 pb-32 md:pb-40">
        <AnimatePresence mode="wait">
          {!chatOpen && (
            <motion.div
              key="voice-bar-visualizer"
              initial={{ opacity: 0, scale: 0.92 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.92, transition: { duration: 0.35 } }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
              className="relative flex flex-col items-center"
            >
              {/* RUPEEGPT branding above the bars */}
              <p className="mb-4 font-sans text-[20px] font-semibold tracking-[0.2em] text-[#d3d0da] drop-shadow-[0_1px_3px_rgba(0,0,0,0.7)] select-none md:text-[22px]">
                RUPEEGPT
              </p>

              {/* Voice energy bars */}
              <div className="relative w-full max-w-[80vw] overflow-visible px-2">
                <VoiceBarVisualizer status={aiLoaderStatus} />
              </div>

              {/* State caption under the bars */}
              <p
                className={cn(
                  'mt-5 font-sans text-[13px] font-medium tracking-wide select-none',
                  aiLoaderStatus === 'speaking'
                    ? 'text-[#c4a7ff]'
                    : aiLoaderStatus === 'listening'
                      ? 'text-[#b7a9d9]'
                      : 'animate-pulse text-[#9a9a9a]'
                )}
              >
                {aiLoaderStatus === 'speaking'
                  ? 'RupeeGPT is speaking'
                  : aiLoaderStatus === 'listening'
                    ? 'RupeeGPT is listening'
                    : 'Connecting to RupeeGPT...'}
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Bottom Control Bar */}
      <motion.div
        {...BOTTOM_VIEW_MOTION_PROPS}
        className="absolute inset-x-3 bottom-0 z-50 md:inset-x-12"
      >
        {/* Pre-connect message */}
        {isPreConnectBufferEnabled && (
          <AnimatePresence>
            {messages.length === 0 && (
              <MotionMessage
                key="pre-connect-message"
                duration={2}
                aria-hidden={messages.length > 0}
                {...SHIMMER_MOTION_PROPS}
                className="pointer-events-none mx-auto block w-full max-w-2xl pb-4 text-center text-sm font-semibold text-[#9a9a9a]"
              >
                {preConnectMessage}
              </MotionMessage>
            )}
          </AnimatePresence>
        )}
        <div className="relative mx-auto max-w-2xl bg-transparent pb-4 md:pb-12">
          <Fade bottom className="absolute inset-x-0 top-0 h-4 -translate-y-full" />
          <AgentControlBar
            variant="livekit"
            controls={controls}
            isChatOpen={chatOpen}
            isConnected={session.isConnected}
            onDisconnect={session.end}
            onIsChatOpenChange={setChatOpen}
            className="border border-white/[0.08] bg-[#0b0b0b]/90 shadow-[0_10px_35px_rgba(0,0,0,0.6)] backdrop-blur-md"
          />
        </div>
      </motion.div>
    </section>
  );
}
