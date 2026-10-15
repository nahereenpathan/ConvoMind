import React, { useState } from 'react';
import { ChevronDown, Plus, Building2, Check } from 'lucide-react';
import { useWorkspaceStore } from '../../stores/useWorkspaceStore';
import { Modal } from '../ui/Modal';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';

export const WorkspaceSelector: React.FC = () => {
  const { workspaces, activeWorkspace, setActiveWorkspace, createWorkspace } =
    useWorkspaceStore();
  const [isOpen, setIsOpen] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [newWorkspaceDesc, setNewWorkspaceDesc] = useState('');
  const [creating, setCreating] = useState(false);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWorkspaceName.trim()) return;
    setCreating(true);
    try {
      await createWorkspace(newWorkspaceName.trim(), newWorkspaceDesc.trim());
      setNewWorkspaceName('');
      setNewWorkspaceDesc('');
      setIsModalOpen(false);
    } catch (err) {
      console.error('Failed to create workspace', err);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full px-3 py-2 text-[14px] rounded-lg bg-[#102C4D] border border-[#1D4E78] hover:bg-[#123456] transition-colors text-[#F8FAFC] font-medium"
      >
        <div className="flex items-center space-x-2.5 truncate">
          <div className="flex items-center justify-center w-6 h-6 rounded bg-[#2563EB]/20 text-[#3B82F6] border border-[#2563EB]/40">
            <Building2 className="w-3.5 h-3.5" />
          </div>
          <span className="truncate font-semibold text-[#F8FAFC]">
            {activeWorkspace ? activeWorkspace.name : 'Select Workspace'}
          </span>
        </div>
        <ChevronDown className={`w-4 h-4 text-[#8FA4BD] transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div
          className="absolute left-0 top-full mt-2 w-full z-50 bg-[#102C4D] border border-[#1D4E78] rounded-xl shadow-2xl py-1.5 animate-fade-in"
          onClick={() => setIsOpen(false)}
        >
          <div className="px-3 py-1.5 text-[11px] font-semibold tracking-wider text-[#8FA4BD] uppercase">
            Workspaces
          </div>

          <div className="max-h-48 overflow-y-auto custom-scrollbar">
            {workspaces.map((ws) => (
              <button
                key={ws.id}
                onClick={() => setActiveWorkspace(ws)}
                className="flex items-center justify-between w-full px-3 py-2 text-[14px] text-left hover:bg-[#123456] transition-colors text-[#B8C7DA] hover:text-[#F8FAFC]"
              >
                <span className="truncate font-medium">{ws.name}</span>
                {activeWorkspace?.id === ws.id && <Check className="w-4 h-4 text-[#3B82F6]" />}
              </button>
            ))}
          </div>

          <div className="border-t border-[#1D4E78] mt-1 pt-1 px-1">
            <button
              onClick={() => {
                setIsOpen(false);
                setIsModalOpen(true);
              }}
              className="flex items-center space-x-2 w-full px-2.5 py-2 text-[14px] font-semibold text-[#3B82F6] hover:bg-[#123456] hover:text-blue-300 rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Create Workspace</span>
            </button>
          </div>
        </div>
      )}

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Create New Workspace"
        description="Workspaces isolate team meetings, transcripts, and AI intelligence."
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <Input
            label="Workspace Name"
            placeholder="e.g. Engineering Team, Marketing"
            value={newWorkspaceName}
            onChange={(e) => setNewWorkspaceName(e.target.value)}
            required
          />
          <Input
            label="Description (Optional)"
            placeholder="What is this workspace for?"
            value={newWorkspaceDesc}
            onChange={(e) => setNewWorkspaceDesc(e.target.value)}
          />
          <div className="flex justify-end space-x-3 pt-2">
            <Button variant="ghost" onClick={() => setIsModalOpen(false)} type="button">
              Cancel
            </Button>
            <Button type="submit" isLoading={creating} disabled={!newWorkspaceName.trim()}>
              Create Workspace
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
