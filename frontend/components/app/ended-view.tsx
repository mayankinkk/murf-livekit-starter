'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/shadcn/utils';

interface EndedViewProps {
  onStartAgain: () => void;
  className?: string;
}

export const EndedView = ({ onStartAgain, className }: EndedViewProps) => {
  return (
    <div
      className={cn(
        'flex h-full w-full flex-col items-center justify-center gap-10 bg-[#050505] px-6 py-14 text-center',
        className
      )}
    >
      <div className="flex w-full max-w-sm flex-col items-center gap-4 rounded-3xl border border-white/[0.06] bg-[#0b0b0b]/80 p-10 shadow-[0_4px_30px_rgba(0,0,0,0.5)] backdrop-blur-md">
        <h2 className="text-2xl font-semibold tracking-wide text-[#f5f5f5] uppercase">
          CONVERSATION ENDED
        </h2>
        <p className="text-sm leading-relaxed font-medium text-[#92929a]">Ready to talk again?</p>
        <Button
          size="lg"
          onClick={onStartAgain}
          className="mt-4 w-full cursor-pointer rounded-full border border-purple-400/20 bg-gradient-to-b from-[#8b5cf6] to-[#6d3fd9] px-8 py-5.5 font-sans text-xs font-semibold tracking-wider text-white shadow-[0_4px_12px_rgba(109,63,217,0.15)] transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_0_20px_rgba(139,92,246,0.3)]"
        >
          START AGAIN
        </Button>
      </div>
    </div>
  );
};
