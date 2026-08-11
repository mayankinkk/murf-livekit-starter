'use client';

import React from 'react';
import { Landmark, Mic, PiggyBank, ShieldCheck, TrendingUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CardSpotlight } from '@/components/ui/card-spotlight';
import { cn } from '@/lib/shadcn/utils';

interface WelcomeViewProps {
  /**
   * Brand heading shown beneath the RupeeGPT logo.
   */
  title: string;
  /**
   * Short tagline shown beneath the title.
   */
  subtitle: string;
  /**
   * Short description shown beneath the subtitle.
   */
  description: string;
  /**
   * Text shown on the Start call button.
   */
  startButtonText: string;
  onStartCall: () => void;
  className?: string;
}

export const WelcomeView = ({
  title,
  subtitle,
  description,
  startButtonText,
  onStartCall,
  className,
  ...props
}: WelcomeViewProps & React.ComponentProps<'div'>) => {
  return (
    <div
      className={cn(
        'relative flex h-full w-full flex-col items-center justify-between overflow-x-hidden overflow-y-auto bg-[#030303] px-6 py-6 md:py-8',
        className
      )}
      {...props}
    >
      {/* Background Depth - Glow and Vignettes */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {/* Radial Purple Glow behind Hero */}
        <div className="absolute top-0 left-1/2 h-[350px] w-[700px] -translate-x-1/2 rounded-full bg-purple-600/[0.025] blur-[90px]" />
        {/* Faint Indigo Glow */}
        <div className="absolute top-[25%] left-[20%] h-[250px] w-[450px] rounded-full bg-indigo-500/[0.012] blur-[90px]" />
      </div>

      {/* Content Center Wrapper */}
      <div className="relative z-10 my-auto flex w-full max-w-2xl flex-col items-center py-10 text-center">
        {/* Hero Title & Subtitle */}
        <h1 className="mt-6 font-sans text-3xl font-bold tracking-tight text-[#f5f5f5] md:text-4xl">
          {title.toUpperCase()}
        </h1>
        <p className="mt-1.5 bg-gradient-to-r from-[#c4a7ff] via-[#f0c8ff] to-[#8b5cf6] bg-clip-text text-[10px] font-semibold tracking-[0.2em] text-transparent uppercase md:text-xs">
          {subtitle}
        </p>

        {/* Hero Supporting Text */}
        <p className="mt-3 max-w-lg px-2 text-xs leading-relaxed text-[#92929a] md:text-sm">
          {description}
        </p>

        {/* Capability indicator */}
        <div className="mt-4 flex items-center justify-center gap-2.5 rounded-full border border-white/[0.04] bg-white/[0.01] px-4 py-1 text-[9px] font-semibold tracking-wider text-[#92929a] uppercase shadow-[0_2px_8px_rgba(0,0,0,0.15)] backdrop-blur-sm select-none md:text-[10px]">
          <span>English</span>
          <span className="font-bold text-[#8b5cf6]/60">•</span>
          <span>Hindi</span>
          <span className="font-bold text-[#8b5cf6]/60">•</span>
          <span>Hinglish</span>
        </div>

        {/* Subtle premium divider */}
        <div className="relative my-6 flex w-full max-w-xs items-center justify-center">
          <div className="absolute inset-0 flex items-center">
            <div className="h-[1px] w-full bg-gradient-to-r from-transparent via-white/5 to-transparent" />
          </div>
          <div className="relative size-1 rounded-full bg-[#8b5cf6] shadow-[0_0_6px_#8b5cf6]" />
        </div>

        {/* Capability Header */}
        <div className="mb-4 flex flex-col items-center">
          <span className="text-[9px] font-semibold tracking-[0.25em] text-[#8b5cf6] uppercase">
            Financial Intelligence
          </span>
          <h2 className="mt-1 text-lg font-medium tracking-wide text-[#f5f5f5]">
            What can RupeeGPT help with?
          </h2>
        </div>

        {/* Cards Grid */}
        <div className="grid w-full gap-3 text-left sm:grid-cols-2">
          {/* Card 1 */}
          <CardSpotlight className="relative flex h-28 flex-col justify-center overflow-hidden rounded-2xl border border-white/[0.04] bg-[#0b0b0b]/60 p-5 transition-all duration-300 hover:border-purple-500/20">
            {/* Micro details: Line graph motif */}
            <svg
              className="pointer-events-none absolute right-2 bottom-2 size-12 text-[#8b5cf6]/[0.02]"
              viewBox="0 0 40 40"
              fill="none"
            >
              <path
                d="M5 32 L12 22 L20 27 L28 12 L35 17"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>

            <div>
              <div className="flex items-center gap-2 text-[#c4a7ff] transition-colors group-hover:text-[#f0c8ff]">
                <Landmark className="size-4 shrink-0" />
                <h3 className="font-sans text-[10px] font-semibold tracking-wider uppercase">
                  Banking & UPI
                </h3>
              </div>
              <p className="mt-2 pr-4 text-[11px] leading-relaxed text-[#92929a]">
                Get guidance on bank accounts, UPI, cards, ATMs, and everyday digital payments.
              </p>
            </div>
          </CardSpotlight>

          {/* Card 2 */}
          <CardSpotlight className="relative flex h-28 flex-col justify-center overflow-hidden rounded-2xl border border-white/[0.04] bg-[#0b0b0b]/60 p-5 transition-all duration-300 hover:border-purple-500/20">
            {/* Micro details: Dot grid */}
            <div className="pointer-events-none absolute top-2 right-2 grid grid-cols-4 gap-0.5 opacity-[0.04]">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="size-0.5 rounded-full bg-[#c4a7ff]" />
              ))}
            </div>

            <div>
              <div className="flex items-center gap-2 text-[#c4a7ff] transition-colors group-hover:text-[#f0c8ff]">
                <PiggyBank className="size-4 shrink-0" />
                <h3 className="font-sans text-[10px] font-semibold tracking-wider uppercase">
                  Savings & Budgeting
                </h3>
              </div>
              <p className="mt-2 pr-4 text-[11px] leading-relaxed text-[#92929a]">
                Plan spending, understand savings options, and build better budgeting habits.
              </p>
            </div>
          </CardSpotlight>

          {/* Card 3 */}
          <CardSpotlight className="relative flex h-28 flex-col justify-center overflow-hidden rounded-2xl border border-white/[0.04] bg-[#0b0b0b]/60 p-5 transition-all duration-300 hover:border-purple-500/20">
            {/* Micro details: Faint ₹ symbol */}
            <span className="pointer-events-none absolute right-3 bottom-1 font-serif text-3xl font-semibold text-[#f0c8ff]/[0.02] select-none">
              ₹
            </span>

            <div>
              <div className="flex items-center gap-2 text-[#c4a7ff] transition-colors group-hover:text-[#f0c8ff]">
                <TrendingUp className="size-4 shrink-0" />
                <h3 className="font-sans text-[10px] font-semibold tracking-wider uppercase">
                  Investments & Loans
                </h3>
              </div>
              <p className="mt-2 pr-4 text-[11px] leading-relaxed text-[#92929a]">
                Learn the basics of investments, loans, credit, interest, and common financial
                products.
              </p>
            </div>
          </CardSpotlight>

          {/* Card 4 */}
          <CardSpotlight className="relative flex h-28 flex-col justify-center overflow-hidden rounded-2xl border border-white/[0.04] bg-[#0b0b0b]/60 p-5 transition-all duration-300 hover:border-purple-500/20">
            {/* Micro details: Faint compass/shield signal */}
            <svg
              className="pointer-events-none absolute right-2 bottom-2 size-10 text-[#8b5cf6]/[0.02]"
              viewBox="0 0 40 40"
              fill="none"
            >
              <circle cx="20" cy="20" r="11" stroke="currentColor" strokeWidth="1.5" />
              <path d="M20 14 V26 M14 20 H26" stroke="currentColor" strokeWidth="1.5" />
            </svg>

            <div>
              <div className="flex items-center gap-2 text-[#c4a7ff] transition-colors group-hover:text-[#f0c8ff]">
                <ShieldCheck className="size-4 shrink-0" />
                <h3 className="font-sans text-[10px] font-semibold tracking-wider uppercase">
                  Financial Safety
                </h3>
              </div>
              <p className="mt-2 pr-4 text-[11px] leading-relaxed text-[#92929a]">
                Learn how to recognize scams and protect yourself from financial fraud.
              </p>
            </div>
          </CardSpotlight>
        </div>

        {/* Language selector indicator */}
        <div className="mt-6 flex flex-col items-center gap-2">
          <span className="text-[9px] font-semibold tracking-[0.2em] text-[#92929a] uppercase select-none">
            Supported Languages
          </span>
          <div className="flex items-center gap-4 rounded-full border border-white/[0.04] bg-white/[0.005] px-5 py-1.5 shadow-[0_2px_8px_rgba(0,0,0,0.25)] select-none">
            <span className="text-[11px] font-medium tracking-wide text-[#f5f5f5]">English</span>
            <span className="h-1 w-1 rounded-full bg-[#8b5cf6]" />
            <span className="text-[11px] font-medium tracking-wide text-[#f5f5f5]">Hindi</span>
            <span className="h-1 w-1 rounded-full bg-[#8b5cf6]" />
            <span className="text-[11px] font-medium tracking-wide text-[#f5f5f5]">Hinglish</span>
          </div>
        </div>

        {/* CTA (Start RupeeGPT Call Button) */}
        <div className="mt-6 flex flex-col items-center gap-2">
          <Button
            size="lg"
            onClick={onStartCall}
            className="group relative cursor-pointer overflow-hidden rounded-full border border-purple-400/20 bg-gradient-to-b from-[#8b5cf6] to-[#6d3fd9] px-8 py-5.5 font-sans text-xs font-semibold tracking-wider text-white shadow-[0_4px_12px_rgba(109,63,217,0.15)] transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_0_20px_rgba(139,92,246,0.3)]"
          >
            {/* Hover highlight overlay */}
            <span className="pointer-events-none absolute inset-0 bg-white/[0.04] opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
            <span className="relative z-10 flex items-center gap-2">
              <Mic className="size-3.5 text-[#f0c8ff] transition-transform duration-300 group-hover:scale-110" />
              {startButtonText.toUpperCase()}
            </span>
          </Button>
          <span className="mt-0.5 text-[10px] tracking-wide text-[#92929a] select-none">
            Your voice. Your questions. Your financial assistant.
          </span>
        </div>

        {/* Product Statement / Subtle Footer */}
        <footer className="mt-8 flex w-full flex-col items-center gap-1 text-center select-none">
          <p className="text-[10px] font-medium tracking-wide text-[#92929a]">
            RupeeGPT &bull; AI-powered financial guidance
          </p>
          <p className="max-w-sm px-4 text-[9px] text-[#92929a]/40">
            Always verify important financial decisions with official sources.
          </p>
        </footer>
      </div>
    </div>
  );
};
