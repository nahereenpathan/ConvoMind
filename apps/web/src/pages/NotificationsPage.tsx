import React, { useState, useEffect } from 'react';
import { Bell, CheckCheck, Clock } from 'lucide-react';
import { notificationsApi } from '../api/notifications';
import { AppNotification } from '../types';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Skeleton } from '../components/ui/Skeleton';

export const NotificationsPage: React.FC = () => {
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchNotifications = async () => {
    setLoading(true);
    try {
      const data = await notificationsApi.getNotifications();
      setNotifications(data);
    } catch (err) {
      console.error('Failed to fetch notifications', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, []);

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch (err) {
      console.error('Failed to mark all read', err);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in text-[#F8FAFC]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-[#F8FAFC]">Notifications</h1>
          <p className="text-xs sm:text-sm text-[#7F94AF] mt-0.5">
            System updates, transcript processing alerts, and AI follow-up notifications.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleMarkAllRead} icon={<CheckCheck />}>
          Mark All Read
        </Button>
      </div>

      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      ) : notifications.length === 0 ? (
        <Card className="p-12 text-center text-[#7F94AF] space-y-3 bg-[#0D2748] border border-[#1E4A78]">
          <Bell className="w-10 h-10 text-[#7F94AF] mx-auto" />
          <p className="text-sm sm:text-base font-semibold text-[#F8FAFC]">No notifications yet</p>
        </Card>
      ) : (
        <div className="space-y-3">
          {notifications.map((n) => (
            <Card
              key={n.id}
              className={`space-y-1.5 bg-[#0D2748] border border-[#1E4A78] ${!n.is_read ? 'border-[#3B82F6] bg-[#102F55]' : ''}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-2">
                  <h4 className="text-sm sm:text-base font-semibold text-[#F8FAFC]">{n.title}</h4>
                  {!n.is_read && <Badge variant="primary" size="sm">New</Badge>}
                </div>
                <span className="text-xs sm:text-sm text-[#7F94AF] flex items-center">
                  <Clock className="w-3.5 h-3.5 mr-1" />
                  {new Date(n.created_at).toLocaleString()}
                </span>
              </div>
              <p className="text-xs sm:text-sm text-[#B8C7DA] leading-relaxed">{n.message}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
