'use client';

import React, { useEffect, useState } from 'react';
import {
  ShieldAlert,
  AlertCircle,
  Phone,
  MessageSquare,
  CheckCircle2,
  Clock,
  User,
  Globe,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Check,
  Building,
  ArrowUpRight
} from 'lucide-react';
import Link from 'next/link';

interface Escalation {
  id: string;
  created_at: string;
  name: string;
  contact_number: string;
  reason: string;
  summary: string;
  urgency: 'Urgent' | 'High' | 'Medium';
  preferred_language: string;
  status: 'Open' | 'Contacted' | 'Resolved';
}

export default function EscalationDashboard() {
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [urgencyFilter, setUrgencyFilter] = useState<string>('all');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchEscalations = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const res = await fetch('/api/escalations');
      if (res.ok) {
        const data = await res.json();
        // Sort by date (newest first) and urgency (Urgent first)
        const sorted = data.sort((a: Escalation, b: Escalation) => {
          if (a.status !== b.status) {
            // Put Open first
            if (a.status === 'Open') return -1;
            if (b.status === 'Open') return 1;
            if (a.status === 'Contacted') return -1;
            if (b.status === 'Contacted') return 1;
          }
          // Then by created_at
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        });
        setEscalations(sorted);
      }
    } catch (err) {
      console.error('Failed to fetch escalations:', err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchEscalations();
    // Poll every 4 seconds to catch new voice escalations in real-time
    const interval = setInterval(() => {
      fetchEscalations(true);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  const updateStatus = async (id: string, newStatus: 'Open' | 'Contacted' | 'Resolved') => {
    try {
      const res = await fetch('/api/escalations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, status: newStatus, statusUpdateOnly: true }),
      });
      if (res.ok) {
        setEscalations(prev =>
          prev.map(e => (e.id === id ? { ...e, status: newStatus } : e))
        );
      }
    } catch (err) {
      console.error('Failed to update status:', err);
    }
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    fetchEscalations();
  };

  // Filter escalations
  const filteredEscalations = escalations.filter(e => {
    const matchesSearch =
      e.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      e.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      e.summary.toLowerCase().includes(searchTerm.toLowerCase()) ||
      e.reason.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus = statusFilter === 'all' || e.status === statusFilter;
    const matchesUrgency = urgencyFilter === 'all' || e.urgency === urgencyFilter;

    return matchesSearch && matchesStatus && matchesUrgency;
  });

  const getUrgencyBadge = (urgency: string) => {
    switch (urgency) {
      case 'Urgent':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20 shadow-[0_0_12px_rgba(244,63,94,0.15)] animate-pulse">
            <AlertCircle className="w-3.5 h-3.5" />
            Urgent
          </span>
        );
      case 'High':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertCircle className="w-3.5 h-3.5" />
            High
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Clock className="w-3.5 h-3.5" />
            Medium
          </span>
        );
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'Resolved':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" />
            Resolved
          </span>
        );
      case 'Contacted':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Clock className="w-3 h-3" />
            In Progress
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-violet-500/10 text-violet-400 border border-violet-500/20 shadow-[0_0_8px_rgba(139,92,246,0.1)]">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-ping mr-1" />
            New / Open
          </span>
        );
    }
  };

  return (
    <main className="min-h-screen bg-[#090514] text-slate-100 font-sans p-6 md:p-12 relative overflow-hidden">
      {/* Background gradients */}
      <div className="absolute top-[-10%] right-[-10%] w-[500px] h-[500px] rounded-full bg-violet-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full bg-fuchsia-600/5 blur-[120px] pointer-events-none" />

      <div className="max-w-6xl mx-auto relative z-10">
        {/* Header */}
        <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-10 border-b border-violet-950/40 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="bg-violet-600/20 p-2.5 rounded-xl border border-violet-500/30 shadow-[0_0_15px_rgba(139,92,246,0.2)]">
                <Building className="w-6 h-6 text-violet-400" />
              </div>
              <div>
                <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight bg-gradient-to-r from-violet-200 via-fuchsia-100 to-slate-200 bg-clip-text text-transparent">
                  RupeeGPT Escalation Desk
                </h1>
                <p className="text-sm text-slate-400">
                  Day 7: Live Voice Agent Human-in-the-Loop Dashboard
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
              href="/dashboard"
              className="px-4 py-2 rounded-xl bg-violet-950/20 hover:bg-violet-900/30 border border-violet-900/40 hover:border-violet-700/40 text-slate-300 text-xs font-semibold transition-all flex items-center gap-1"
            >
              Call Analytics <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
            <div className="flex items-center gap-2 text-xs text-slate-400 bg-[#120b24] px-3.5 py-2 rounded-xl border border-violet-950/60">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span>Live Monitoring Active</span>
            </div>
            <button
              onClick={handleRefresh}
              className={`p-2.5 rounded-xl bg-violet-900/20 hover:bg-violet-900/40 border border-violet-800/30 hover:border-violet-700/40 transition-all text-violet-300 ${
                isRefreshing ? 'animate-spin' : ''
              }`}
              title="Refresh Queue"
            >
              <RefreshCw className="w-4.5 h-4.5" />
            </button>
          </div>
        </header>

        {/* Toolbar & Filters */}
        <section className="bg-[#100a20]/90 border border-violet-950/60 rounded-2xl p-4 mb-6 flex flex-col md:flex-row gap-4 items-center justify-between backdrop-blur-md">
          {/* Search */}
          <div className="relative w-full md:w-80">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search by ID, name, details..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-xl bg-[#090514] border border-violet-950/60 focus:border-violet-700/50 focus:ring-1 focus:ring-violet-700/30 outline-none text-slate-200 placeholder-slate-500 transition-all text-sm"
            />
          </div>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-3 w-full md:w-auto justify-end">
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <SlidersHorizontal className="w-3.5 h-3.5 text-violet-400" />
              <span>Filters:</span>
            </div>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="bg-[#090514] border border-violet-950/60 rounded-xl px-3 py-1.5 text-xs text-slate-300 outline-none focus:border-violet-700/50"
            >
              <option value="all">All Statuses</option>
              <option value="Open">Open</option>
              <option value="Contacted">In Progress</option>
              <option value="Resolved">Resolved</option>
            </select>

            {/* Urgency Filter */}
            <select
              value={urgencyFilter}
              onChange={e => setUrgencyFilter(e.target.value)}
              className="bg-[#090514] border border-violet-950/60 rounded-xl px-3 py-1.5 text-xs text-slate-300 outline-none focus:border-violet-700/50"
            >
              <option value="all">All Urgency</option>
              <option value="Urgent">Urgent Only</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
            </select>
          </div>
        </section>

        {/* Escalations Grid */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <RefreshCw className="w-8 h-8 text-violet-500 animate-spin" />
            <p className="text-slate-400 text-sm">Fetching escalation queue...</p>
          </div>
        ) : filteredEscalations.length === 0 ? (
          <div className="bg-[#100a20]/40 border border-violet-950/40 rounded-2xl p-16 text-center">
            <CheckCircle2 className="w-12 h-12 text-violet-500/40 mx-auto mb-4" />
            <h3 className="text-lg font-bold text-slate-300 mb-1">Queue is Clear!</h3>
            <p className="text-slate-500 text-sm max-w-sm mx-auto">
              No active customer escalations matching your filters. Make a call and report a fraud or request a loan raise to trigger one!
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {filteredEscalations.map(escalation => (
              <article
                key={escalation.id}
                className={`bg-[#100a20]/95 border rounded-2xl p-5 md:p-6 transition-all duration-300 flex flex-col justify-between hover:translate-y-[-2px] hover:shadow-[0_8px_30px_rgb(15,10,28)] ${
                  escalation.status === 'Resolved'
                    ? 'border-violet-950/40 opacity-60'
                    : escalation.urgency === 'Urgent'
                    ? 'border-rose-950/60 shadow-[0_0_15px_rgba(244,63,94,0.04)] hover:border-rose-800/40'
                    : 'border-violet-950/60 hover:border-violet-800/40'
                }`}
              >
                {/* Card Header */}
                <div>
                  <div className="flex justify-between items-start gap-4 mb-4">
                    <span className="font-mono text-xs font-bold text-violet-400 bg-violet-950/40 px-2.5 py-1 rounded-lg border border-violet-900/30">
                      {escalation.id}
                    </span>
                    <div className="flex gap-2">
                      {getUrgencyBadge(escalation.urgency)}
                      {getStatusBadge(escalation.status)}
                    </div>
                  </div>

                  <h3 className="text-lg font-bold text-slate-100 mb-2 flex items-center gap-2">
                    {escalation.reason === 'Possible Fraud / Unauthorized Transaction' ? (
                      <ShieldAlert className="w-5 h-5 text-rose-400 flex-shrink-0" />
                    ) : (
                      <Building className="w-5 h-5 text-amber-400 flex-shrink-0" />
                    )}
                    {escalation.reason}
                  </h3>

                  <p className="text-sm text-slate-300 bg-[#090514]/60 p-3.5 rounded-xl border border-violet-950/40 mb-4 font-normal leading-relaxed">
                    {escalation.summary}
                  </p>
                </div>

                {/* Details Footer */}
                <div className="mt-4 border-t border-violet-950/40 pt-4 flex flex-col gap-3">
                  <div className="grid grid-cols-2 gap-y-2 gap-x-4 text-xs">
                    <div className="flex items-center gap-1.5 text-slate-400">
                      <User className="w-3.5 h-3.5 text-violet-400" />
                      <span className="font-semibold text-slate-300 truncate">
                        {escalation.name}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 text-slate-400 justify-end">
                      <Globe className="w-3.5 h-3.5 text-violet-400" />
                      <span className="text-slate-300">
                        {escalation.preferred_language}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 text-slate-400 col-span-2 mt-1">
                      <Phone className="w-3.5 h-3.5 text-violet-400" />
                      <span className="text-slate-300 font-mono">
                        {escalation.contact_number}
                      </span>
                    </div>
                  </div>

                  <div className="text-[10px] text-slate-500 font-mono flex justify-between items-center mt-2">
                    <span>
                      {new Date(escalation.created_at).toLocaleDateString()} at{' '}
                      {new Date(escalation.created_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </span>
                  </div>

                  {/* Actions */}
                  {escalation.status !== 'Resolved' && (
                    <div className="flex gap-2.5 mt-3 pt-1">
                      {escalation.status === 'Open' && (
                        <button
                          onClick={() => updateStatus(escalation.id, 'Contacted')}
                          className="flex-1 py-2 px-3 rounded-xl bg-violet-900/30 hover:bg-violet-900/50 border border-violet-800/40 hover:border-violet-700/50 transition-all text-xs font-semibold text-violet-200 flex items-center justify-center gap-1.5"
                        >
                          <Phone className="w-3.5 h-3.5" />
                          Mark Contacted
                        </button>
                      )}
                      <button
                        onClick={() => updateStatus(escalation.id, 'Resolved')}
                        className={`py-2 px-3 rounded-xl transition-all text-xs font-semibold flex items-center justify-center gap-1.5 ${
                          escalation.status === 'Contacted'
                            ? 'flex-1 bg-emerald-600 hover:bg-emerald-500 text-white shadow-[0_0_12px_rgba(16,185,129,0.15)]'
                            : 'bg-emerald-950/20 hover:bg-emerald-950/40 border border-emerald-900/30 hover:border-emerald-800/40 text-emerald-400'
                        }`}
                      >
                        <Check className="w-3.5 h-3.5" />
                        Resolve Request
                      </button>
                    </div>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
