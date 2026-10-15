import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  CheckCheck,
  Clock,
  MoreVertical,
  Trash2,
  Check,
  AlertTriangle,
  Loader2,
  MailCheck,
  MailWarning,
} from 'lucide-react';
import { notificationsApi } from '../../api/notifications';
import { AppNotification } from '../../types';
import { Badge } from '../ui/Badge';

export const NotificationDropdown: React.FC = () => {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [showClearModal, setShowClearModal] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const dropdownRef = useRef<HTMLDivElement>(null);

  const fetchNotifications = async () => {
    try {
      const data = await notificationsApi.getNotifications();
      setNotifications(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to fetch notifications', err);
      setNotifications([]);
    }
  };

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, []);

  // Close active dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setActiveMenuId(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const safeNotifications = Array.isArray(notifications) ? notifications : [];
  const unreadCount = safeNotifications.filter((n) => !n.is_read).length;

  const handleMarkAllRead = async () => {
    try {
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      await notificationsApi.markAllAsRead();
    } catch (err) {
      console.error('Failed to mark all as read', err);
      fetchNotifications();
    }
  };

  const handleMarkAsRead = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setActiveMenuId(null);
    try {
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      await notificationsApi.markAsRead(id);
    } catch (err) {
      console.error('Failed to mark notification as read', err);
      fetchNotifications();
    }
  };

  const handleMarkAsUnread = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setActiveMenuId(null);
    try {
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: false } : n))
      );
      await notificationsApi.markAsUnread(id);
    } catch (err) {
      console.error('Failed to mark notification as unread', err);
      fetchNotifications();
    }
  };

  const handleDeleteIndividual = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setActiveMenuId(null);
    const previousNotifications = [...notifications];

    // Optimistic UI update
    setNotifications((prev) => prev.filter((n) => n.id !== id));

    try {
      await notificationsApi.deleteNotification(id);
    } catch (err) {
      console.error('Failed to delete notification', err);
      setNotifications(previousNotifications);
      setErrorMessage('Unable to delete notification.');
      setTimeout(() => setErrorMessage(null), 3000);
    }
  };

  const handleClearAll = async () => {
    setIsClearing(true);
    const previousNotifications = [...notifications];
    setNotifications([]);

    try {
      await notificationsApi.clearAllNotifications();
      setShowClearModal(false);
    } catch (err) {
      console.error('Failed to clear notifications', err);
      setNotifications(previousNotifications);
      setErrorMessage('Unable to clear notifications.');
      setTimeout(() => setErrorMessage(null), 3000);
    } finally {
      setIsClearing(false);
    }
  };

  const handleNotificationClick = (n: AppNotification) => {
    if (!n.is_read) {
      handleMarkAsRead(n.id);
    }

    if (n.entity_type === 'meeting' && n.entity_id) {
      navigate(`/meetings/${n.entity_id}`);
      setIsOpen(false);
    } else if (n.entity_type === 'follow_up' && n.entity_id) {
      if (n.notification_metadata?.meeting_id) {
        navigate(`/meetings/${n.notification_metadata.meeting_id}`);
      } else {
        navigate('/meetings');
      }
      setIsOpen(false);
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-lg text-[#7F94AF] hover:text-[#F8FAFC] hover:bg-[#102F55] transition-colors"
        title="Notifications"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 flex h-4 w-4 items-center justify-center rounded-full bg-blue-600 text-[10px] font-bold text-white shadow-sm animate-pulse">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-80 sm:w-96 z-50 bg-[#0D2748] border border-[#1E4A78] rounded-xl shadow-2xl overflow-hidden animate-fade-in text-[#F8FAFC]">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#1E4A78] bg-[#0A1F3D]">
            <div className="flex items-center space-x-2">
              <h4 className="text-sm font-semibold text-[#F8FAFC]">Notifications</h4>
              {unreadCount > 0 && <Badge variant="primary" size="sm">{unreadCount} new</Badge>}
            </div>

            <div className="flex items-center space-x-3 text-xs">
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  className="text-blue-400 hover:text-blue-300 font-medium flex items-center space-x-1 transition-colors"
                >
                  <CheckCheck className="w-3.5 h-3.5" />
                  <span>Mark all read</span>
                </button>
              )}
              {safeNotifications.length > 0 && (
                <button
                  onClick={() => setShowClearModal(true)}
                  className="text-red-400 hover:text-red-300 font-medium flex items-center space-x-1 transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Clear All</span>
                </button>
              )}
            </div>
          </div>

          {/* Error Banner */}
          {errorMessage && (
            <div className="bg-red-500/20 border-b border-red-500/40 text-red-300 px-4 py-2 text-xs flex items-center justify-between">
              <span>{errorMessage}</span>
            </div>
          )}

          {/* List Content */}
          <div className="max-h-80 overflow-y-auto custom-scrollbar divide-y divide-[#1E4A78]">
            {safeNotifications.length === 0 ? (
              <div className="p-8 text-center text-[#7F94AF]">
                <div className="w-10 h-10 mx-auto mb-2 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-400">
                  <Check className="w-5 h-5" />
                </div>
                <h5 className="text-xs font-semibold text-[#F8FAFC]">You're all caught up</h5>
                <p className="text-[11px] text-[#7F94AF] mt-0.5">No new notifications.</p>
              </div>
            ) : (
              safeNotifications.map((n) => {
                const isMenuOpen = activeMenuId === n.id;
                return (
                  <div
                    key={n.id}
                    onClick={() => handleNotificationClick(n)}
                    className={`group relative p-3.5 hover:bg-[#102F55] transition-colors cursor-pointer ${
                      !n.is_read ? 'bg-[#102F55]/60' : ''
                    }`}
                  >
                    <div className="flex items-start justify-between space-x-2">
                      <div className="flex items-center space-x-1.5 flex-1 min-w-0">
                        {/* Unread indicator dot */}
                        {!n.is_read ? (
                          <span className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0 animate-pulse" />
                        ) : (
                          <span className="w-2 h-2 rounded-full bg-transparent flex-shrink-0" />
                        )}
                        <h5 className={`text-xs font-semibold truncate ${!n.is_read ? 'text-[#F8FAFC]' : 'text-[#B8C7DA]'}`}>
                          {n.title}
                        </h5>
                      </div>

                      <div className="flex items-center space-x-2 flex-shrink-0">
                        <span className="text-[10px] text-[#7F94AF] flex items-center">
                          <Clock className="w-3 h-3 mr-0.5" />
                          {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>

                        {/* Three-dot menu trigger */}
                        <div className="relative">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveMenuId(isMenuOpen ? null : n.id);
                            }}
                            className="p-1 rounded text-[#7F94AF] hover:text-[#F8FAFC] hover:bg-[#1E4A78] transition-colors"
                            title="Options"
                          >
                            <MoreVertical className="w-3.5 h-3.5" />
                          </button>

                          {/* Contextual Menu */}
                          {isMenuOpen && (
                            <div className="absolute right-0 top-6 z-20 w-36 bg-[#0A1F3D] border border-[#1E4A78] rounded-lg shadow-xl py-1 text-xs text-[#F8FAFC] animate-fade-in">
                              {n.is_read ? (
                                <button
                                  onClick={(e) => handleMarkAsUnread(n.id, e)}
                                  className="w-full text-left px-3 py-1.5 hover:bg-[#102F55] flex items-center space-x-2 text-[#B8C7DA] hover:text-white"
                                >
                                  <MailWarning className="w-3.5 h-3.5 text-blue-400" />
                                  <span>Mark Unread</span>
                                </button>
                              ) : (
                                <button
                                  onClick={(e) => handleMarkAsRead(n.id, e)}
                                  className="w-full text-left px-3 py-1.5 hover:bg-[#102F55] flex items-center space-x-2 text-[#B8C7DA] hover:text-white"
                                >
                                  <MailCheck className="w-3.5 h-3.5 text-blue-400" />
                                  <span>Mark Read</span>
                                </button>
                              )}
                              <button
                                onClick={(e) => handleDeleteIndividual(n.id, e)}
                                className="w-full text-left px-3 py-1.5 hover:bg-red-500/20 text-red-400 hover:text-red-300 flex items-center space-x-2"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                                <span>Delete</span>
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    <p className="text-xs text-[#B8C7DA] mt-1 pl-3.5 line-clamp-2">{n.message}</p>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* Clear All Confirmation Modal */}
      {showClearModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-[#0D2748] border border-[#1E4A78] rounded-xl max-w-sm w-full p-5 shadow-2xl text-[#F8FAFC]">
            <div className="flex items-center space-x-3 text-amber-400 mb-3">
              <AlertTriangle className="w-6 h-6" />
              <h3 className="text-base font-semibold">Clear all notifications?</h3>
            </div>
            <p className="text-xs text-[#B8C7DA] mb-5">
              This will remove all notifications from your notification list.
            </p>
            <div className="flex items-center justify-end space-x-3">
              <button
                onClick={() => setShowClearModal(false)}
                disabled={isClearing}
                className="px-3.5 py-2 rounded-lg text-xs font-medium text-[#7F94AF] hover:bg-[#102F55] transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleClearAll}
                disabled={isClearing}
                className="px-4 py-2 rounded-lg text-xs font-medium bg-red-600 hover:bg-red-500 text-white transition-colors flex items-center space-x-1 disabled:opacity-50"
              >
                {isClearing ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                    <span>Clearing...</span>
                  </>
                ) : (
                  <span>Clear All</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
