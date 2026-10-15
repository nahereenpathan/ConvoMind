import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Calendar, Clock, ChevronRight, MoreVertical, Trash2, Eye, RotateCcw } from 'lucide-react';
import { Meeting, MeetingStatus } from '../../types';
import { Card } from '../ui/Card';
import { Badge, BadgeVariant } from '../ui/Badge';

interface MeetingCardProps {
  meeting: Meeting;
  onMoveToTrash?: (meeting: Meeting) => void;
  onRestore?: (meeting: Meeting) => void;
  onPermanentDelete?: (meeting: Meeting) => void;
}

export const MeetingCard: React.FC<MeetingCardProps> = ({
  meeting,
  onMoveToTrash,
  onRestore,
  onPermanentDelete,
}) => {
  const navigate = useNavigate();
  const [showMenu, setShowMenu] = useState(false);

  const getStatusBadge = (status: MeetingStatus) => {
    const config: Record<MeetingStatus, { label: string; variant: BadgeVariant }> = {
      [MeetingStatus.SCHEDULED]: { label: 'Scheduled', variant: 'info' },
      [MeetingStatus.IN_PROGRESS]: { label: 'In Progress', variant: 'warning' },
      [MeetingStatus.RECORDING]: { label: 'Recording', variant: 'warning' },
      [MeetingStatus.PROCESSING]: { label: 'Processing AI', variant: 'warning' },
      [MeetingStatus.COMPLETED]: { label: 'Ready', variant: 'success' },
      [MeetingStatus.FAILED]: { label: 'Failed', variant: 'danger' },
      [MeetingStatus.CANCELLED]: { label: 'Cancelled', variant: 'default' },
    };
    const c = config[status] || { label: status, variant: 'default' };
    return <Badge variant={c.variant}>{c.label}</Badge>;
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return null;
    const mins = Math.floor(seconds / 60);
    return `${mins} min`;
  };

  const isTrashed = !!meeting.deleted_at;

  return (
    <Card
      hover
      onClick={() => navigate(`/meetings/${meeting.id}`)}
      className="flex flex-col justify-between space-y-4 group bg-[#102C4D] border border-[#1D4E78] shadow-lg hover:shadow-xl transition-all p-5 relative"
    >
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-[16px] sm:text-[18px] font-bold text-[#F8FAFC] group-hover:text-[#3B82F6] transition-colors line-clamp-1 pr-6">
            {meeting.title}
          </h3>

          <div className="flex items-center space-x-2 shrink-0">
            {getStatusBadge(meeting.status)}

            {/* Contextual 3-Dot Menu Button */}
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowMenu((prev) => !prev);
                }}
                className="p-1 rounded-lg hover:bg-[#123456] text-[#8FA4BD] hover:text-[#F8FAFC] transition-colors"
                title="Meeting Options"
              >
                <MoreVertical className="w-5 h-5" />
              </button>

              {showMenu && (
                <div
                  onClick={(e) => e.stopPropagation()}
                  className="absolute right-0 top-8 w-44 bg-[#0A1B35] border border-[#1D4E78] rounded-xl shadow-2xl py-1.5 z-40 text-[13px] animate-fade-in"
                >
                  <button
                    onClick={() => {
                      setShowMenu(false);
                      navigate(`/meetings/${meeting.id}`);
                    }}
                    className="w-full text-left px-3.5 py-2 hover:bg-[#123456] text-[#F8FAFC] flex items-center space-x-2 font-medium"
                  >
                    <Eye className="w-4 h-4 text-[#3B82F6]" />
                    <span>View Details</span>
                  </button>

                  {!isTrashed && onMoveToTrash && (
                    <button
                      onClick={() => {
                        setShowMenu(false);
                        onMoveToTrash(meeting);
                      }}
                      className="w-full text-left px-3.5 py-2 hover:bg-[#EF4444]/20 text-[#EF4444] flex items-center space-x-2 font-medium border-t border-[#1D4E78]/50"
                    >
                      <Trash2 className="w-4 h-4 text-[#EF4444]" />
                      <span>Move to Trash</span>
                    </button>
                  )}

                  {isTrashed && onRestore && (
                    <button
                      onClick={() => {
                        setShowMenu(false);
                        onRestore(meeting);
                      }}
                      className="w-full text-left px-3.5 py-2 hover:bg-[#123456] text-[#22C55E] flex items-center space-x-2 font-medium border-t border-[#1D4E78]/50"
                    >
                      <RotateCcw className="w-4 h-4 text-[#22C55E]" />
                      <span>Restore Meeting</span>
                    </button>
                  )}

                  {isTrashed && onPermanentDelete && (
                    <button
                      onClick={() => {
                        setShowMenu(false);
                        onPermanentDelete(meeting);
                      }}
                      className="w-full text-left px-3.5 py-2 hover:bg-[#EF4444]/20 text-[#EF4444] flex items-center space-x-2 font-medium border-t border-[#1D4E78]/50"
                    >
                      <Trash2 className="w-4 h-4 text-[#EF4444]" />
                      <span>Delete Permanently</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-2">
          {meeting.is_native ? (
            <span className="inline-flex items-center text-[11px] font-bold text-[#3B82F6] bg-[#2563EB]/15 border border-[#2563EB]/30 px-2 py-0.5 rounded-md">
              🎥 Native Meeting
            </span>
          ) : (
            <span className="inline-flex items-center text-[11px] font-bold text-[#8FA4BD] bg-[#123456] border border-[#1D4E78] px-2 py-0.5 rounded-md">
              📁 Uploaded Recording
            </span>
          )}

          {isTrashed && (
            <span className="inline-flex items-center text-[11px] font-bold text-[#EF4444] bg-[#EF4444]/15 border border-[#EF4444]/30 px-2 py-0.5 rounded-md">
              🗑 In Trash
            </span>
          )}
        </div>

        {meeting.description && (
          <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] line-clamp-2 leading-relaxed font-normal">
            {meeting.description}
          </p>
        )}
      </div>

      <div className="flex items-center justify-between text-[13px] sm:text-[14px] text-[#8FA4BD] border-t border-[#1D4E78] pt-3.5">
        <div className="flex items-center space-x-3">
          <span className="flex items-center space-x-1.5">
            <Calendar className="w-4 h-4 text-[#8FA4BD]" />
            <span>{formatDate(meeting.created_at)}</span>
          </span>
          {meeting.duration_seconds ? (
            <span className="flex items-center space-x-1.5">
              <Clock className="w-4 h-4 text-[#8FA4BD]" />
              <span>{formatDuration(meeting.duration_seconds)}</span>
            </span>
          ) : null}
        </div>

        <div className="flex items-center space-x-2">
          {meeting.is_native && !isTrashed && meeting.status !== MeetingStatus.COMPLETED && meeting.status !== MeetingStatus.CANCELLED && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                navigate(`/meetings/${meeting.id}/live`);
              }}
              className="text-[13px] font-bold text-white bg-[#2563EB] hover:bg-[#1D4ED8] px-3 py-1 rounded-lg transition-colors flex items-center space-x-1 shadow-sm"
            >
              <span>Join Live Room</span>
            </button>
          )}
          <div className="flex items-center space-x-1 text-[#3B82F6] group-hover:text-blue-300 group-hover:translate-x-1 transition-all font-semibold text-[14px]">
            <span>View Details</span>
            <ChevronRight className="w-4 h-4" />
          </div>
        </div>
      </div>
    </Card>
  );
};
