import React, { useState, useEffect } from 'react';
import { Mail, Send, CheckCircle2, Sparkles, AlertTriangle, AlertCircle, Copy, Check } from 'lucide-react';
import { FollowUpEmail } from '../../types';
import { followUpsApi } from '../../api/followups';
import { Modal } from '../ui/Modal';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';

interface FollowUpModalProps {
  meetingId: string;
  isOpen: boolean;
  onClose: () => void;
}

export const FollowUpModal: React.FC<FollowUpModalProps> = ({ meetingId, isOpen, onClose }) => {
  const [followUp, setFollowUp] = useState<FollowUpEmail | null>(null);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [recipients, setRecipients] = useState('');
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [sentSuccess, setSentSuccess] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setError(null);
      setSentSuccess(false);
      setFollowUp(null);
      setSubject('');
      setBody('');
      setRecipients('');
      setGenerating(false);
      fetchFollowUp();
    }
  }, [isOpen, meetingId]);

  const getErrorMessage = (err: any, fallback: string): string => {
    const detail = err?.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((d: any) => d?.msg || JSON.stringify(d)).join(', ');
    }
    if (detail && typeof detail === 'object') {
      return detail.message || detail.error || JSON.stringify(detail);
    }
    return err?.message || fallback;
  };

  const fetchFollowUp = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await followUpsApi.getFollowUps(meetingId);
      if (list.length > 0) {
        const item = list[0];
        setFollowUp(item);
        setSubject(item.subject);
        setBody(item.body);
        setRecipients((item.recipients || []).join(', '));
      } else {
        setFollowUp(null);
      }
    } catch (err: any) {
      console.error('Failed to fetch follow-up', err);
      setError(getErrorMessage(err, 'Unable to load existing follow-up draft.'));
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async (e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    if (generating || loading) return;
    setGenerating(true);
    setError(null);
    setSentSuccess(false);
    try {
      const item = await followUpsApi.generateFollowUp(meetingId);
      setFollowUp(item);
      setSubject(item.subject);
      setBody(item.body);
      setRecipients((item.recipients || []).join(', '));
      setError(null);
    } catch (err: any) {
      console.error('Failed to generate follow-up', err);
      setError(getErrorMessage(err, 'Unable to generate the follow-up email.'));
    } finally {
      setGenerating(false);
    }
  };

  const handleCopyDraft = () => {
    const fullText = `Subject: ${subject}\n\n${body}`;
    navigator.clipboard.writeText(fullText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSave = async () => {
    if (!followUp || saving) return;
    setSaving(true);
    setError(null);
    try {
      const recipientList = recipients.split(',').map((r) => r.trim()).filter(Boolean);
      const updated = await followUpsApi.updateFollowUp(followUp.id, {
        subject,
        body,
        recipients: recipientList,
      });
      setFollowUp(updated);
    } catch (err: any) {
      console.error('Failed to update follow-up', err);
      setError(getErrorMessage(err, 'Unable to save follow-up draft changes.'));
    } finally {
      setSaving(false);
    }
  };

  const handleSend = async () => {
    if (!followUp || sending) return;
    setSending(true);
    setError(null);
    setSentSuccess(false);
    try {
      await handleSave();
      await followUpsApi.sendFollowUp(followUp.id);
      setSentSuccess(true);
      setFollowUp((prev) => (prev ? { ...prev, status: 'SENT' } : null));
    } catch (err: any) {
      console.error('Failed to send follow-up', err);
      setSentSuccess(false);
      setError(getErrorMessage(err, 'Unable to send follow-up email.'));
    } finally {
      setSending(false);
    }
  };

  const modalFooter = followUp && !loading && !generating ? (
    <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 w-full">
      <div className="flex items-center space-x-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleGenerate}
          isLoading={generating}
          icon={<Sparkles className="w-4 h-4" />}
        >
          Regenerate AI Draft
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleCopyDraft}
          icon={copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
        >
          {copied ? 'Copied!' : 'Copy Draft'}
        </Button>
      </div>

      {followUp.status !== 'SENT' && (
        <div className="flex items-center space-x-3 justify-end">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleSave}
            isLoading={saving}
          >
            Save Draft
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={handleSend}
            isLoading={sending}
            icon={<Send className="w-4 h-4" />}
          >
            Send Follow-Up
          </Button>
        </div>
      )}
    </div>
  ) : null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="AI Meeting Follow-Up Email"
      description="Draft and dispatch AI-generated meeting follow-ups to participants with Human-in-the-Loop review."
      maxWidth="720px"
      footer={modalFooter}
    >
      <div className="space-y-4 text-[#F8FAFC]">
        {error && (
          <div className="p-3 bg-[#EF4444]/15 border border-[#EF4444]/40 text-[13px] sm:text-[14px] text-[#EF4444] rounded-lg font-medium flex items-start space-x-2.5">
            <AlertCircle className="w-4 h-4 text-[#EF4444] shrink-0 mt-0.5" />
            <div className="flex-1">
              <span className="font-semibold text-rose-200">Delivery Error: </span>
              {error}
            </div>
          </div>
        )}

        {loading || generating ? (
          <div className="py-12 px-6 text-center text-[#B8C7DA] text-[14px] space-y-3">
            <Sparkles className="w-8 h-8 text-[#818CF8] mx-auto animate-spin" />
            <p className="font-semibold text-[#F8FAFC] text-[16px]">Generating AI Follow-Up Email Draft...</p>
            <p className="text-[13px] text-[#8FA4BD]">Extracting summary, decisions, action items, and recipient contacts.</p>
          </div>
        ) : !followUp ? (
          <div className="p-8 text-center bg-[#123456] rounded-xl border border-[#1D4E78] space-y-4">
            <Mail className="w-10 h-10 text-[#818CF8] mx-auto" />
            <div className="space-y-1">
              <p className="font-semibold text-[16px] text-[#F8FAFC]">No follow-up email generated yet</p>
              <p className="text-[13px] sm:text-[14px] text-[#8FA4BD]">
                Instantly create an AI-synthesized follow-up draft based on meeting transcript, action items, and decisions.
              </p>
            </div>
            <Button
              type="button"
              onClick={handleGenerate}
              isLoading={generating}
              disabled={generating || loading}
              icon={<Sparkles />}
            >
              {generating ? 'Generating draft...' : 'Generate Draft Follow-Up'}
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Human in the loop notification alert */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-[#F59E0B]/15 border border-[#F59E0B]/40 text-[13px] sm:text-[14px] text-[#F59E0B]">
              <div className="flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-[#F59E0B] shrink-0" />
                <span>
                  <strong className="text-amber-200">Human Review Required:</strong> AI drafted this email. Review and edit before sending.
                </span>
              </div>
              <Badge variant={followUp.status === 'SENT' ? 'success' : 'warning'}>
                {followUp.status}
              </Badge>
            </div>

            {sentSuccess && (
              <div className="flex items-center space-x-2 p-3 bg-[#22C55E]/15 border border-[#22C55E]/40 text-[13px] sm:text-[14px] text-[#22C55E] rounded-lg font-medium">
                <CheckCircle2 className="w-4 h-4 text-[#22C55E] shrink-0" />
                <span>Follow-up email dispatched successfully!</span>
              </div>
            )}

            <Input
              label="Recipients (comma separated)"
              value={recipients}
              onChange={(e) => setRecipients(e.target.value)}
              placeholder="e.g. john@acme.com, sarah@acme.com"
              disabled={followUp.status === 'SENT' || sending}
            />

            <Input
              label="Subject Line"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Subject"
              disabled={followUp.status === 'SENT' || sending}
            />

            <div className="space-y-1.5">
              <label className="block text-[14px] sm:text-[15px] font-semibold text-[#B8C7DA]">Email Body</label>
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                className="w-full h-[220px] sm:h-[280px] bg-[#123456] border border-[#1D4E78] rounded-lg p-3.5 text-[15px] sm:text-[16px] leading-[1.6] text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6] custom-scrollbar resize-none disabled:bg-[#0A1B35]"
                disabled={followUp.status === 'SENT' || sending}
              />
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};
