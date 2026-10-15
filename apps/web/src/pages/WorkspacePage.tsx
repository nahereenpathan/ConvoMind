import React, { useState, useEffect } from 'react';
import { UserPlus, Trash2, Mail, Check } from 'lucide-react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { workspaceApi } from '../api/workspace';
import { WorkspaceMember, UserRole } from '../types';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { Avatar } from '../components/ui/Avatar';

export const WorkspacePage: React.FC = () => {
  const { activeWorkspace, updateWorkspace } = useWorkspaceStore();
  const [members, setMembers] = useState<WorkspaceMember[]>([]);

  const [wsName, setWsName] = useState(activeWorkspace?.name || '');
  const [wsDesc, setWsDesc] = useState(activeWorkspace?.description || '');
  const [savingWs, setSavingWs] = useState(false);

  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<UserRole>(UserRole.MEMBER);
  const [inviting, setInviting] = useState(false);

  const fetchMembers = async () => {
    if (!activeWorkspace) return;
    try {
      const data = await workspaceApi.getMembers(activeWorkspace.id);
      setMembers(data);
    } catch (err) {
      console.error('Failed to fetch members', err);
    }
  };

  useEffect(() => {
    if (activeWorkspace) {
      setWsName(activeWorkspace.name);
      setWsDesc(activeWorkspace.description || '');
      fetchMembers();
    }
  }, [activeWorkspace]);

  const handleUpdateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspace || !wsName.trim()) return;
    setSavingWs(true);
    try {
      await updateWorkspace(activeWorkspace.id, wsName.trim(), wsDesc.trim());
    } catch (err) {
      console.error('Failed to update workspace', err);
    } finally {
      setSavingWs(false);
    }
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspace || !inviteEmail.trim()) return;
    setInviting(true);
    try {
      await workspaceApi.addMember(activeWorkspace.id, inviteEmail.trim(), inviteRole);
      setInviteEmail('');
      setIsAddModalOpen(false);
      fetchMembers();
    } catch (err) {
      console.error('Failed to add member', err);
    } finally {
      setInviting(false);
    }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!activeWorkspace) return;
    try {
      await workspaceApi.removeMember(activeWorkspace.id, userId);
      fetchMembers();
    } catch (err) {
      console.error('Failed to remove member', err);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in text-[#F8FAFC]">
      <div>
        <h1 className="text-[26px] sm:text-[30px] font-bold text-[#F8FAFC]">Workspace Settings</h1>
        <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] mt-1">
          Manage workspace details, team members, and role-based access control (RBAC).
        </p>
      </div>

      <Card className="bg-[#102C4D] border border-[#1D4E78]">
        <h3 className="text-[18px] sm:text-[20px] font-bold text-[#F8FAFC] mb-4">Workspace Info</h3>
        <form onSubmit={handleUpdateWorkspace} className="space-y-4">
          <Input
            label="Workspace Name"
            value={wsName}
            onChange={(e) => setWsName(e.target.value)}
            required
          />

          <div className="space-y-1.5">
            <label className="block text-[13px] sm:text-[14px] font-semibold text-[#B8C7DA]">Description</label>
            <textarea
              value={wsDesc}
              onChange={(e) => setWsDesc(e.target.value)}
              rows={3}
              className="w-full bg-[#123456] border border-[#1D4E78] rounded-lg p-3 text-[14px] sm:text-[15px] text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6]"
            />
          </div>

          <div className="flex justify-end">
            <Button type="submit" isLoading={savingWs} icon={<Check />}>
              Save Workspace Changes
            </Button>
          </div>
        </form>
      </Card>

      <Card className="space-y-4 bg-[#102C4D] border border-[#1D4E78]">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-[18px] sm:text-[20px] font-bold text-[#F8FAFC]">Workspace Members</h3>
            <p className="text-[13px] sm:text-[14px] text-[#B8C7DA]">Team members with access to this workspace</p>
          </div>
          <Button onClick={() => setIsAddModalOpen(true)} icon={<UserPlus />}>
            Add Member
          </Button>
        </div>

        <div className="divide-y divide-[#1D4E78]">
          {members.map((m) => (
            <div key={m.id} className="py-3 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <Avatar name={m.user?.full_name || m.user?.email || 'User'} size="md" />
                <div>
                  <h4 className="text-[14px] sm:text-[15px] font-semibold text-[#F8FAFC]">
                    {m.user?.full_name || 'Member'}
                  </h4>
                  <p className="text-[12px] sm:text-[13px] text-[#8FA4BD]">{m.user?.email}</p>
                </div>
              </div>

              <div className="flex items-center space-x-3">
                <Badge variant={m.role === UserRole.OWNER ? 'primary' : m.role === UserRole.ADMIN ? 'info' : 'default'}>
                  {m.role}
                </Badge>

                {m.role !== UserRole.OWNER && (
                  <button
                    onClick={() => handleRemoveMember(m.user_id)}
                    className="p-1.5 text-[#8FA4BD] hover:text-[#EF4444] hover:bg-[#123456] rounded transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="Add Workspace Member"
        description="Invite an existing user to collaborate in this workspace."
      >
        <form onSubmit={handleAddMember} className="space-y-4">
          <Input
            label="User Email Address"
            type="email"
            placeholder="colleague@company.com"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            icon={<Mail />}
            required
          />

          <div className="space-y-1.5">
            <label className="block text-[13px] sm:text-[14px] font-semibold text-[#B8C7DA]">Assign Role</label>
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as UserRole)}
              className="w-full bg-[#123456] border border-[#1D4E78] rounded-lg p-2.5 text-[13px] sm:text-[14px] text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6]"
            >
              <option value={UserRole.MEMBER}>Member (Read & Process Meetings)</option>
              <option value={UserRole.ADMIN}>Admin (Manage Members & Settings)</option>
            </select>
          </div>

          <div className="flex justify-end space-x-3 pt-2">
            <Button variant="ghost" type="button" onClick={() => setIsAddModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={inviting} disabled={!inviteEmail.trim()}>
              Add Member
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
