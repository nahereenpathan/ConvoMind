import React, { useState } from 'react';
import { User as UserIcon, Mail, Check, Key } from 'lucide-react';
import { useAuthStore } from '../stores/useAuthStore';
import { authApi } from '../api/auth';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';

export const SettingsPage: React.FC = () => {
  const { user, setUser } = useAuthStore();
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSavedSuccess(false);

    try {
      const updated = await authApi.updateProfile({ full_name: fullName });
      setUser(updated);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to update profile', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in text-[#F8FAFC]">
      <div>
        <h1 className="text-[26px] sm:text-[30px] font-bold text-[#F8FAFC]">Account Settings</h1>
        <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] mt-1">Manage your personal profile and account credentials.</p>
      </div>

      <Card className="bg-[#102C4D] border border-[#1D4E78]">
        <h3 className="text-[18px] sm:text-[20px] font-bold text-[#F8FAFC] mb-4">Profile Information</h3>

        <form onSubmit={handleSaveProfile} className="space-y-4">
          {savedSuccess && (
            <div className="p-3 bg-[#22C55E]/15 border border-[#22C55E]/40 text-[13px] sm:text-[14px] text-[#22C55E] font-medium rounded-lg">
              Profile updated successfully!
            </div>
          )}

          <Input
            label="Full Name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            icon={<UserIcon />}
          />

          <Input
            label="Email Address"
            value={user?.email || ''}
            disabled
            icon={<Mail />}
            helperText="Email address cannot be changed."
          />

          <div className="flex justify-end pt-2">
            <Button type="submit" isLoading={saving} icon={<Check />}>
              Save Settings
            </Button>
          </div>
        </form>
      </Card>

      <Card className="space-y-3 bg-[#102C4D] border border-[#1D4E78]">
        <div className="flex items-center space-x-3 text-[#3B82F6] font-semibold text-[15px] sm:text-[16px]">
          <Key className="w-4.5 h-4.5" />
          <span>Security & Authentication</span>
        </div>
        <p className="text-[13px] sm:text-[14px] text-[#8FA4BD] leading-relaxed">
          Your session is secured using OAuth2 JWT access & refresh tokens with workspace RBAC enforcement.
        </p>
      </Card>
    </div>
  );
};
