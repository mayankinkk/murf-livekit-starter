'use client';

import { useEffect, useState } from 'react';
import { ConnectionState, MediaDeviceFailure } from 'livekit-client';
import { SessionEvent, useAgent, useSessionContext } from '@livekit/components-react';
import type { AiLoaderStatus } from '@/components/ui/ai-loader';

export interface UseVoiceAgentStatusReturn {
  /**
   * Derived voice agent state used to drive the RupeeGPT loader and status pills.
   */
  status: AiLoaderStatus;
  /**
   * `true` when the browser denied access to the user's microphone.
   */
  micPermissionDenied: boolean;
  /**
   * Dismiss the microphone permission banner.
   */
  clearMicPermissionError: () => void;
  /**
   * Retry starting the audio session (used by the microphone error banner).
   */
  retryStart: () => Promise<void>;
}

/**
 * Derives a single, UI-friendly RupeeGPT Voice agent status from the LiveKit
 * session and agent context, and tracks microphone permission failures.
 *
 * Status mapping:
 * - idle before the first call     -> `ready`
 * - real room/agent booting        -> `connecting`
 * - agent waiting for user speech  -> `listening`
 * - agent synthesizing a reply     -> `speaking`
 * - the call has ended             -> `ended`
 *
 * The "connecting" state is driven directly by the LiveKit `ConnectionState`
 * (Connecting / Reconnecting / SignalReconnecting) — i.e. the period between
 * the user pressing START and `isConnected` becoming `true`. No timers or
 * fake delays are used.
 */
export function useVoiceAgentStatus(): UseVoiceAgentStatusReturn {
  const session = useSessionContext();
  const agent = useAgent(session);
  const [hasConnectedOnce, setHasConnectedOnce] = useState(false);
  const [micPermissionDenied, setMicPermissionDenied] = useState(false);

  // Track whether a previous call ever fully connected so we can distinguish
  // "ready" (never connected) from "ended" (a previous call was dropped).
  useEffect(() => {
    if (session.isConnected) {
      setHasConnectedOnce(true);
    }
  }, [session.isConnected]);

  // Surface microphone permission errors raised by the LiveKit session.
  useEffect(() => {
    const onMediaDevicesError = (error: Error) => {
      if (MediaDeviceFailure.getFailure(error) === MediaDeviceFailure.PermissionDenied) {
        setMicPermissionDenied(true);
      }
    };

    session.internal.emitter.on(SessionEvent.MediaDevicesError, onMediaDevicesError);
    return () => {
      session.internal.emitter.off(SessionEvent.MediaDevicesError, onMediaDevicesError);
    };
  }, [session]);

  let status: AiLoaderStatus;
  if (session.isConnected) {
    switch (agent.state) {
      case 'listening':
        status = 'listening';
        break;
      case 'thinking':
      case 'speaking':
        status = 'speaking';
        break;
      default:
        status = 'connecting';
    }
  } else if (
    (session.connectionState as string) === ConnectionState.Connecting ||
    (session.connectionState as string) === ConnectionState.Reconnecting ||
    (session.connectionState as string) === ConnectionState.SignalReconnecting
  ) {
    status = 'connecting';
  } else {
    status = hasConnectedOnce ? 'ended' : 'ready';
  }

  return {
    status,
    micPermissionDenied,
    clearMicPermissionError: () => setMicPermissionDenied(false),
    retryStart: async () => {
      setMicPermissionDenied(false);
      await session.start();
    },
  };
}
