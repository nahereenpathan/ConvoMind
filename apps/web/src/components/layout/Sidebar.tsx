import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Video,
  PlusCircle,
  CheckSquare,
  Users,
  Settings,
  CreditCard,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { WorkspaceSelector } from './WorkspaceSelector';
import { systemApi, AiEngineHealthResponse } from '../../api/system';
import { AiEngineStatusModal } from '../system/AiEngineStatusModal';

export const Sidebar: React.FC = () => {
  const [health, setHealth] = useState<AiEngineHealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  const fetchHealth = async (forceRefresh = false) => {
    setLoading(true);
    try {
      const data = await systemApi.getAiEngineHealth(forceRefresh);
      setHealth(data);
      setError(null);
    } catch (err: any) {
      console.warn('[Sidebar] Unable to fetch AI Engine health:', err?.response?.status || err?.message);
      setError('Unable to reach AI health API');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    // Auto-refresh every 45 seconds
    const interval = setInterval(() => {
      fetchHealth();
    }, 45000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { label: 'Dashboard', path: '/', icon: LayoutDashboard },
    { label: 'Meetings', path: '/meetings', icon: Video },
    { label: 'Trash', path: '/trash', icon: Trash2 },
    { label: 'New Meeting', path: '/meetings/new', icon: PlusCircle },
    { label: 'Action Items', path: '/action-items', icon: CheckSquare },
    { label: 'Workspace', path: '/workspace', icon: Users },
    { label: 'Billing & Plans', path: '/billing', icon: CreditCard },
    { label: 'Settings', path: '/settings', icon: Settings },
  ];

  const getStatusBadge = () => {
    if (error || !health) {
      return (
        <span className="flex items-center text-[#8FA4BD] text-[12px] font-semibold">
          <span className="w-2 h-2 rounded-full bg-[#8FA4BD] mr-1.5" />
          Unavailable
        </span>
      );
    }

    switch (health.overall_status) {
      case 'operational':
        return (
          <span className="flex items-center text-[#22C55E] text-[12px] font-semibold">
            <span className="w-2 h-2 rounded-full bg-[#22C55E] mr-1.5 animate-pulse" />
            Operational
          </span>
        );
      case 'degraded':
        return (
          <span className="flex items-center text-[#F59E0B] text-[12px] font-semibold">
            <span className="w-2 h-2 rounded-full bg-[#F59E0B] mr-1.5 animate-pulse" />
            Degraded
          </span>
        );
      case 'down':
        return (
          <span className="flex items-center text-[#EF4444] text-[12px] font-semibold">
            <span className="w-2 h-2 rounded-full bg-[#EF4444] mr-1.5 animate-pulse" />
            Down
          </span>
        );
      case 'not_configured':
        return (
          <span className="flex items-center text-[#8FA4BD] text-[12px] font-semibold">
            <span className="w-2 h-2 rounded-full bg-[#8FA4BD] mr-1.5" />
            Unconfigured
          </span>
        );
      default:
        return (
          <span className="flex items-center text-[#8FA4BD] text-[12px] font-semibold">
            <span className="w-2 h-2 rounded-full bg-[#8FA4BD] mr-1.5" />
            Unavailable
          </span>
        );
    }
  };

  const getSubtitle = () => {
    if (!health?.components) return 'Whisper • Diarization • RAG';

    const activeServices: string[] = [];
    if (health.components.whisper?.status === 'operational') activeServices.push('Whisper');
    if (health.components.diarization?.status === 'operational') activeServices.push('Diarization');
    if (health.components.rag?.status === 'operational') activeServices.push('RAG');

    if (activeServices.length > 0) {
      return activeServices.join(' • ');
    }
    return 'Whisper • Diarization • RAG';
  };

  return (
    <>
      <aside className="w-64 bg-[#0A1B35] border-r border-[#1D4E78] flex flex-col h-screen sticky top-0 shadow-xl z-30 text-[#B8C7DA]">
        {/* Brand Header */}
        <div className="p-4 border-b border-[#1D4E78]">
          <div className="flex items-center space-x-3">
            <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-[#2563EB] text-white shadow-md border border-[#3B82F6]/50">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-[18px] font-bold text-[#F8FAFC] tracking-tight leading-tight">
                ConvoMind
              </h1>
              <p className="text-[12px] text-[#8FA4BD] font-medium">AI Meeting Intelligence</p>
            </div>
          </div>
        </div>

        {/* Workspace Switcher */}
        <div className="p-3 border-b border-[#1D4E78]">
          <WorkspaceSelector />
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto custom-scrollbar">
          <div className="px-3 py-1.5 text-[11px] font-semibold text-[#8FA4BD] uppercase tracking-wider">
            Main Menu
          </div>
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center space-x-3 px-3 py-2.5 rounded-lg text-[15px] transition-all duration-150 group ${
                  isActive
                    ? 'bg-[#123456] text-[#F8FAFC] font-semibold border-l-4 border-[#3B82F6] shadow-sm'
                    : 'text-[#B8C7DA] hover:text-[#F8FAFC] hover:bg-[#102C4D] font-medium'
                }`
              }
            >
              <item.icon className="w-5 h-5 text-[#8FA4BD] group-hover:text-[#F8FAFC] transition-colors shrink-0" />
              <span className="truncate">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Footer / Interactive System Status Card */}
        <div className="p-3 border-t border-[#1D4E78]">
          <button
            onClick={() => setIsModalOpen(true)}
            className="w-full text-left p-3 rounded-xl bg-[#102C4D] hover:bg-[#123456] border border-[#1D4E78] hover:border-[#3B82F6]/50 text-[13px] text-[#B8C7DA] space-y-1 shadow-inner transition-all group cursor-pointer"
          >
            <div className="flex items-center justify-between font-semibold text-[#F8FAFC]">
              <span className="flex items-center space-x-1.5 text-[13px] font-bold group-hover:text-[#3B82F6] transition-colors">
                <Sparkles className="w-4 h-4 text-[#3B82F6]" />
                <span>AI Engine</span>
              </span>
              {getStatusBadge()}
            </div>
            <p className="text-[12px] text-[#8FA4BD] truncate">{getSubtitle()}</p>
          </button>
        </div>
      </aside>

      {/* Interactive AI Engine Status Modal */}
      <AiEngineStatusModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        health={health}
        loading={loading}
        error={error}
        onRefresh={() => fetchHealth(true)}
      />
    </>
  );
};
