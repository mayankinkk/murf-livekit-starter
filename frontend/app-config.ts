export interface AppConfig {
  pageTitle: string;
  pageDescription: string;
  companyName: string;

  welcomeTitle: string;
  welcomeSubtitle: string;
  welcomeDescription: string;

  supportsChatInput: boolean;
  supportsVideoInput: boolean;
  supportsScreenShare: boolean;
  isPreConnectBufferEnabled: boolean;

  logo: string;
  startButtonText: string;
  accent?: string;
  logoDark?: string;
  accentDark?: string;

  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorDark?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerBarCount?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerWaveLineWidth?: number;

  // agent dispatch configuration
  agentName?: string;

  // LiveKit Cloud Sandbox configuration
  sandboxId?: string;
}

export const APP_CONFIG_DEFAULTS: AppConfig = {
  companyName: 'RupeeGPT Voice',
  pageTitle: 'RupeeGPT Voice',
  pageDescription:
    'Your AI financial voice assistant for India — banking, UPI, savings, loans and financial safety, made simple.',

  welcomeTitle: 'RupeeGPT',
  welcomeSubtitle: 'Your AI Financial Voice Assistant',
  welcomeDescription: 'Talk to RupeeGPT about banking, UPI, savings, loans and financial safety.',

  supportsChatInput: true,
  supportsVideoInput: true,
  supportsScreenShare: true,
  isPreConnectBufferEnabled: false,

  logo: '/rupegpt-logo.png',
  accent: '#7C3AED',
  logoDark: '/rupegpt-logo.png',
  accentDark: '#8B5CF6',
  startButtonText: 'Start RupeeGPT',

  // audio visualization configuration
  audioVisualizerType: 'radial',
  audioVisualizerColor: '#8B5CF6',
  audioVisualizerColorDark: '#A78BFA',
  audioVisualizerColorShift: 0.3,
  audioVisualizerBarCount: 5,
  audioVisualizerRadialBarCount: 36,
  audioVisualizerRadialRadius: 110,

  // agent dispatch configuration
  agentName: process.env.AGENT_NAME ?? undefined,

  // LiveKit Cloud Sandbox configuration
  sandboxId: undefined,
};
