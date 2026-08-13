'use client';

import React, { useEffect, useState } from 'react';
import {
  Phone,
  CheckCircle2,
  XCircle,
  Clock,
  RefreshCw,
  SlidersHorizontal,
  Activity,
  ArrowUpRight,
  ShieldAlert,
  HelpCircle,
  Globe,
  Monitor,
  Trash2,
  Play
} from 'lucide-react';
import Link from 'next/link';

interface CallRecord {
  id: string;
  created_at: string;
  ended_at: string;
  duration_seconds: number;
  success: boolean;
  success_reason: string;
  call_type: 'web' | 'sip';
  user_id: string;
}

export default function CallDashboard() {
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [outcomeFilter, setOutcomeFilter] = useState<string>('all');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchCalls = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const res = await fetch('/api/calls');
      if (res.ok) {
        const data = await res.json();
        // Sort by ended_at (newest first)
        const sorted = data.sort(
          (a: CallRecord, b: CallRecord) =>
            new Date(b.ended_at).getTime() - new Date(a.ended_at).getTime()
        );
        setCalls(sorted);
      }
    } catch (err) {
      console.error('Failed to fetch calls:', err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchCalls();
    // Poll every 3 seconds to update call states instantly during tests
    const interval = setInterval(() => {
      fetchCalls(true);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = () => {
    setIsRefreshing(true);
    fetchCalls();
  };

  // Simulation handler
  const handleSimulate = async (success: boolean) => {
    const randomId = `sim-room-${Math.random().toString(36).substring(2, 9)}`;
    const randomDuration = Math.random() * 80 + 10; // 10s to 90s
    const endedAt = new Date().toISOString();
    const createdAt = new Date(Date.now() - randomDuration * 1000).toISOString();
    const reasons = [
      'Checked government schemes eligibility (Simulated)',
      'Created human escalation: ESC-492716 (Simulated)',
      'Checked banking info & lending rates (Simulated)'
    ];

    const record = {
      id: randomId,
      created_at: createdAt,
      ended_at: endedAt,
      duration_seconds: Math.round(randomDuration * 100) / 100,
      success,
      success_reason: success ? reasons[Math.floor(Math.random() * reasons.length)] : '',
      call_type: Math.random() > 0.3 ? 'web' : 'sip',
      user_id: `sim-user-${Math.floor(Math.random() * 899 + 100)}`
    };

    try {
      const res = await fetch('/api/calls', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(record)
      });
      if (res.ok) {
        fetchCalls(true);
      }
    } catch (err) {
      console.error('Failed to simulate call:', err);
    }
  };

  // Reset handler
  const handleReset = async () => {
    try {
      const res = await fetch('/api/calls', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'reset' })
      });
      if (res.ok) {
        fetchCalls();
      }
    } catch (err) {
      console.error('Failed to reset calls:', err);
    }
  };

  // Filtered lists
  const filteredCalls = calls.filter(c => {
    const matchesType = typeFilter === 'all' || c.call_type === typeFilter;
    const matchesOutcome =
      outcomeFilter === 'all' ||
      (outcomeFilter === 'success' && c.success) ||
      (outcomeFilter === 'failed' && !c.success);

    return matchesType && matchesOutcome;
  });

  // Calculate metrics
  const totalCalls = filteredCalls.length;
  const successfulCalls = filteredCalls.filter(c => c.success).length;
  const failedCalls = totalCalls - successfulCalls;
  const successRate = totalCalls > 0 ? Math.round((successfulCalls / totalCalls) * 100) : 0;

  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  const getCallTypeIcon = (type: string) => {
    if (type === 'sip') {
      return (
        <span className="flex items-center gap-1 text-slate-400 bg-amber-500/10 px-2 py-1 rounded-lg border border-amber-500/20 text-xs">
          <Globe className="w-3.5 h-3.5 text-amber-400" />
          SIP Agent
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1 text-slate-400 bg-blue-500/10 px-2 py-1 rounded-lg border border-blue-500/20 text-xs">
        <Monitor className="w-3.5 h-3.5 text-blue-400" />
        Browser Agent
      </span>
    );
  };

  return (
    <main className="min-h-screen bg-[#090514] text-slate-100 font-sans p-6 md:p-12 relative overflow-hidden">
      {/* Background gradients */}
      <div className="absolute top-[-10%] right-[-10%] w-[500px] h-[500px] rounded-full bg-violet-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full bg-fuchsia-600/5 blur-[120px] pointer-events-none" />

      <div className="max-w-6xl mx-auto relative z-10">
        {/* Navigation & Header */}
        <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-10 border-b border-violet-950/40 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="bg-violet-600/20 p-2.5 rounded-xl border border-violet-500/30 shadow-[0_0_15px_rgba(139,92,246,0.2)]">
                <Activity className="w-6 h-6 text-violet-400 animate-pulse" />
              </div>
              <div>
                <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight bg-gradient-to-r from-violet-200 via-fuchsia-100 to-slate-200 bg-clip-text text-transparent">
                  RupeeGPT Call Analytics
                </h1>
                <p className="text-sm text-slate-400">
                  Day 8: Real-time Call Performance & Success Monitoring
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 self-stretch md:self-auto justify-between md:justify-start">
            <Link
              href="/"
              className="px-4 py-2 rounded-xl bg-violet-950/20 hover:bg-violet-900/30 border border-violet-900/40 hover:border-violet-700/40 text-slate-300 text-xs font-semibold transition-all flex items-center gap-1"
            >
              Voice Agent <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
            <Link
              href="/demo"
              className="px-4 py-2 rounded-xl bg-violet-950/20 hover:bg-violet-900/30 border border-violet-900/40 hover:border-violet-700/40 text-slate-300 text-xs font-semibold transition-all flex items-center gap-1"
            >
              Escalation Desk <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
            <button
              onClick={handleRefresh}
              className={`p-2.5 rounded-xl bg-violet-900/20 hover:bg-violet-900/40 border border-violet-800/30 hover:border-violet-700/40 transition-all text-violet-300 ${
                isRefreshing ? 'animate-spin' : ''
              }`}
              title="Refresh Stats"
            >
              <RefreshCw className="w-4.5 h-4.5" />
            </button>
          </div>
        </header>


        {/* Metrics Grid */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
          {/* Card 1: Total Calls */}
          <div className="bg-[#100a20]/90 border border-violet-950/60 rounded-2xl p-5 md:p-6 backdrop-blur-md relative overflow-hidden flex flex-col justify-between hover:border-violet-800/40 transition-all">
            <div className="absolute top-0 right-0 w-24 h-24 bg-violet-500/5 rounded-bl-full pointer-events-none" />
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Total Calls</span>
                <Phone className="w-5 h-5 text-violet-400" />
              </div>
              <div className="text-3xl md:text-4xl font-black text-slate-100 tracking-tight mb-1">
                {totalCalls}
              </div>
            </div>
            <p className="text-[11px] text-slate-500 mt-2">All connected voice sessions</p>
          </div>

          {/* Card 2: Success Rate */}
          <div className="bg-[#100a20]/90 border border-violet-950/60 rounded-2xl p-5 md:p-6 backdrop-blur-md relative overflow-hidden flex flex-col justify-between hover:border-violet-800/40 transition-all">
            <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-bl-full pointer-events-none" />
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Success Rate</span>
                <Activity className="w-5 h-5 text-emerald-400" />
              </div>
              <div className="text-3xl md:text-4xl font-black text-emerald-400 tracking-tight mb-1">
                {successRate}%
              </div>
            </div>
            {/* Simple progress bar */}
            <div className="w-full bg-[#090514] rounded-full h-1.5 mt-2 overflow-hidden border border-violet-950/60">
              <div
                className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                style={{ width: `${successRate}%` }}
              />
            </div>
          </div>

          {/* Card 3: Successful Calls */}
          <div className="bg-[#100a20]/90 border border-violet-950/60 rounded-2xl p-5 md:p-6 backdrop-blur-md relative overflow-hidden flex flex-col justify-between hover:border-violet-800/40 transition-all">
            <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-bl-full pointer-events-none" />
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Successful Calls</span>
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              </div>
              <div className="text-3xl md:text-4xl font-black text-slate-100 tracking-tight mb-1">
                {successfulCalls}
              </div>
            </div>
            <p className="text-[11px] text-slate-500 mt-2">Checked schemes or escalated</p>
          </div>

          {/* Card 4: Failed Calls */}
          <div className="bg-[#100a20]/90 border border-violet-950/60 rounded-2xl p-5 md:p-6 backdrop-blur-md relative overflow-hidden flex flex-col justify-between hover:border-violet-800/40 transition-all">
            <div className="absolute top-0 right-0 w-24 h-24 bg-rose-500/5 rounded-bl-full pointer-events-none" />
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Failed Calls</span>
                <XCircle className="w-5 h-5 text-rose-400" />
              </div>
              <div className="text-3xl md:text-4xl font-black text-slate-100 tracking-tight mb-1">
                {failedCalls}
              </div>
            </div>
            <p className="text-[11px] text-slate-500 mt-2">Did not reach success criteria</p>
          </div>
        </section>

        {/* Toolbar & Filters */}
        <section className="bg-[#100a20]/90 border border-violet-950/60 rounded-2xl p-4 mb-6 flex flex-col sm:flex-row gap-4 items-center justify-between backdrop-blur-md">
          <div className="flex items-center gap-2 text-sm text-slate-300 font-bold">
            <SlidersHorizontal className="w-4 h-4 text-violet-400" />
            <span>Filter Call Logs</span>
          </div>

          <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto justify-end">
            {/* Type Filter */}
            <select
              value={typeFilter}
              onChange={e => setTypeFilter(e.target.value)}
              className="bg-[#090514] border border-violet-950/60 rounded-xl px-3 py-1.5 text-xs text-slate-300 outline-none focus:border-violet-700/50"
            >
              <option value="all">All Call Types</option>
              <option value="web">Browser Only</option>
              <option value="sip">SIP Only</option>
            </select>

            {/* Outcome Filter */}
            <select
              value={outcomeFilter}
              onChange={e => setOutcomeFilter(e.target.value)}
              className="bg-[#090514] border border-violet-950/60 rounded-xl px-3 py-1.5 text-xs text-slate-300 outline-none focus:border-violet-700/50"
            >
              <option value="all">All Outcomes</option>
              <option value="success">Successful</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </section>

        {/* Call Logs Table */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <RefreshCw className="w-8 h-8 text-violet-500 animate-spin" />
            <p className="text-slate-400 text-sm">Fetching call records...</p>
          </div>
        ) : filteredCalls.length === 0 ? (
          <div className="bg-[#100a20]/40 border border-violet-950/40 rounded-2xl p-16 text-center">
            <Phone className="w-12 h-12 text-violet-500/40 mx-auto mb-4" />
            <h3 className="text-lg font-bold text-slate-300 mb-1">No Calls Recorded</h3>
            <p className="text-slate-500 text-sm max-w-sm mx-auto">
              Start the voice assistant and speak to it to test. Check your eligibility or ask for human escalation to register a successful call.
            </p>
          </div>
        ) : (
          <div className="bg-[#100a20]/90 border border-violet-950/60 rounded-2xl overflow-hidden backdrop-blur-md">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="border-b border-violet-950/60 bg-violet-950/20 text-slate-400 text-xs font-semibold tracking-wider">
                    <th className="p-4 pl-6">Call ID</th>
                    <th className="p-4">Type</th>
                    <th className="p-4">Duration</th>
                    <th className="p-4">Time</th>
                    <th className="p-4">Status</th>
                    <th className="p-4 pr-6">Primary Activity / Outcome</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-violet-950/40 text-slate-300 text-sm">
                  {filteredCalls.map(call => (
                    <tr
                      key={call.id}
                      className="hover:bg-violet-950/10 transition-colors"
                    >
                      <td className="p-4 pl-6 font-mono text-xs text-violet-400 font-semibold">
                        {call.id.substring(0, 15)}...
                      </td>
                      <td className="p-4">{getCallTypeIcon(call.call_type)}</td>
                      <td className="p-4 text-xs font-mono flex items-center gap-1.5 mt-1">
                        <Clock className="w-3.5 h-3.5 text-violet-500" />
                        {formatDuration(call.duration_seconds)}
                      </td>
                      <td className="p-4 text-xs">
                        {new Date(call.ended_at).toLocaleDateString()} at{' '}
                        {new Date(call.ended_at).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit'
                        })}
                      </td>
                      <td className="p-4">
                        {call.success ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            <CheckCircle2 className="w-3 h-3" />
                            Success
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                            <XCircle className="w-3 h-3" />
                            Failed
                          </span>
                        )}
                      </td>
                      <td className="p-4 pr-6 text-xs text-slate-400">
                        {call.success ? (
                          <span className="text-emerald-400/90 font-medium">
                            {call.success_reason}
                          </span>
                        ) : (
                          <span className="italic text-slate-500">
                            Call hung up without reaching objectives (Checked eligibility / Escalated)
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
