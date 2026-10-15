import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  CheckSquare,
  FileText,
  HelpCircle,
  Check,
  Clock,
  User,
  RefreshCw,
  AlertTriangle,
  BookmarkCheck,
  Lightbulb,
  ListChecks,
} from 'lucide-react';
import { IntelligenceResult, ActionItemStatus } from '../../types';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { intelligenceApi } from '../../api/intelligence';
import { getErrorMessage } from '../../utils/error';

interface IntelligenceViewProps {
  meetingId: string;
  intelligence: IntelligenceResult | null;
  onRefresh: () => void;
}

export const IntelligenceView: React.FC<IntelligenceViewProps> = ({
  meetingId,
  intelligence,
  onRefresh,
}) => {
  const [generating, setGenerating] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  const pollJobCompletion = async (jobId?: string) => {
    let attempts = 0;
    const maxAttempts = 30; // 45 seconds total
    while (attempts < maxAttempts) {
      try {
        const job = await intelligenceApi.getIntelligenceStatus(meetingId, jobId);
        if (job.status === 'COMPLETED') {
          return true;
        }
        if (job.status === 'FAILED') {
          throw new Error(job.error_message || 'AI Intelligence processing failed. Please retry.');
        }
      } catch (err: any) {
        if (err?.response?.status === 404) {
          // Retry
        } else if (err?.message) {
          throw err;
        }
      }
      attempts++;
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
    throw new Error('AI analysis request timed out. Please retry.');
  };

  useEffect(() => {
    let isSubscribed = true;
    const checkJobStatus = async () => {
      if (intelligence && intelligence.summary) return;
      try {
        const job = await intelligenceApi.getIntelligenceStatus(meetingId);
        if (!isSubscribed) return;
        if (job.status === 'QUEUED' || job.status === 'PROCESSING') {
          setGenerating(true);
          setIsError(false);
          setStatusMessage('Extracting key insights and action items...');
          try {
            await pollJobCompletion(job.id);
            if (isSubscribed) {
              setStatusMessage(null);
              setIsError(false);
              await onRefresh();
            }
          } catch (err: any) {
            if (isSubscribed) {
              setIsError(true);
              setStatusMessage(err?.message || 'AI analysis failed. Please retry.');
            }
          } finally {
            if (isSubscribed) setGenerating(false);
          }
        } else if (job.status === 'FAILED') {
          setIsError(true);
          setStatusMessage(job.error_message || 'AI analysis failed. Please retry.');
        }
      } catch {
        // No job found yet
      }
    };
    checkJobStatus();
    return () => {
      isSubscribed = false;
    };
  }, [meetingId, intelligence]);

  const handleGenerate = async () => {
    setGenerating(true);
    setIsError(false);
    setStatusMessage('Triggering AI Analysis...');
    try {
      const job = await intelligenceApi.generateIntelligence(meetingId);
      setStatusMessage('Extracting key insights and action items...');
      await pollJobCompletion(job.id);
      setStatusMessage(null);
      setIsError(false);
      await onRefresh();
    } catch (err: any) {
      console.error('Failed to generate intelligence', err);
      setIsError(true);
      setStatusMessage(getErrorMessage(err) || 'AI analysis failed. Please retry.');
    } finally {
      setGenerating(false);
    }
  };

  const handleToggleActionItem = async (itemId: string, currentStatus: ActionItemStatus) => {
    const newStatus =
      currentStatus === ActionItemStatus.COMPLETED
        ? ActionItemStatus.OPEN
        : ActionItemStatus.COMPLETED;
    try {
      await intelligenceApi.updateActionItemStatus(itemId, newStatus);
      onRefresh();
    } catch (err) {
      console.error('Failed to update action item status', err);
    }
  };

  if (!intelligence || (!intelligence.summary && (!intelligence.action_items || intelligence.action_items.length === 0))) {
    return (
      <div className="p-12 text-center bg-[#102C4D] border border-[#1D4E78] rounded-2xl space-y-4 shadow-xl text-[#F8FAFC]">
        <div className="p-4 rounded-full bg-[#6366F1]/20 text-[#818CF8] w-16 h-16 mx-auto flex items-center justify-center border border-[#6366F1]/40">
          <Sparkles className="w-8 h-8" />
        </div>
        <div>
          <h3 className="text-[18px] sm:text-[20px] font-bold text-[#F8FAFC]">No Intelligence Generated Yet</h3>
          <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] mt-1 max-w-md mx-auto">
            Extract executive summary, key decisions, action items, risks, and open questions using ConvoMind AI.
          </p>
          {statusMessage && (
            <div className={`p-3 rounded-lg text-[14px] font-medium mt-3 max-w-lg mx-auto flex items-center justify-center space-x-2 ${
              isError
                ? 'bg-[#EF4444]/15 border border-[#EF4444]/40 text-[#EF4444]'
                : 'bg-[#6366F1]/15 border border-[#6366F1]/40 text-[#818CF8]'
            }`}>
              {isError ? <AlertTriangle className="w-4 h-4 shrink-0 text-[#EF4444]" /> : <RefreshCw className="w-4 h-4 animate-spin shrink-0 text-[#818CF8]" />}
              <span>{statusMessage}</span>
            </div>
          )}
        </div>
        <Button variant="ai" onClick={handleGenerate} isLoading={generating} icon={<Sparkles />}>
          {isError ? 'Retry AI Intelligence' : 'Generate AI Intelligence'}
        </Button>
      </div>
    );
  }

  const summary = intelligence.summary;
  const executiveSummary = summary?.overview || summary?.summary_text || '';
  const detailedSummary = summary?.detailed_summary || '';

  // Helper parser for string or object arrays
  const parseList = (list: any[] | undefined): string[] => {
    if (!list) return [];
    return list
      .map((item) => {
        if (typeof item === 'string') return item;
        if (typeof item === 'object' && item !== null) {
          return item.point || item.step || item.risk || item.note || item.suggestion || Object.values(item)[0] || '';
        }
        return '';
      })
      .filter((s) => Boolean(s));
  };

  const keyPoints = parseList(summary?.key_points);
  const risks = parseList(summary?.risks_and_concerns);
  const requirements = parseList(summary?.requirements_and_notes);
  const followUps = parseList(summary?.follow_up_suggestions);

  return (
    <div className="space-y-6 text-[#F8FAFC]">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <Sparkles className="w-5 h-5 text-[#818CF8]" />
          <h3 className="text-[18px] sm:text-[20px] font-bold text-[#F8FAFC]">AI Meeting Insights</h3>
        </div>
        <Button variant="outline" size="sm" onClick={handleGenerate} isLoading={generating} icon={<RefreshCw />}>
          Re-analyze
        </Button>
      </div>

      {statusMessage && (
        <div className="p-3 bg-[#6366F1]/15 border border-[#6366F1]/40 rounded-lg text-[14px] text-[#818CF8] flex items-center space-x-2">
          <RefreshCw className="w-4 h-4 animate-spin text-[#818CF8]" />
          <span>{statusMessage}</span>
        </div>
      )}

      {/* 1. Executive Summary */}
      {executiveSummary && (
        <Card className="border-[#6366F1]/40 bg-[#6366F1]/10 shadow-md">
          <div className="flex items-center space-x-2 mb-2.5 text-[#818CF8] font-bold text-[16px] sm:text-[18px]">
            <FileText className="w-5 h-5 text-[#818CF8]" />
            <span>Executive Summary</span>
          </div>
          <p className="text-[15px] sm:text-[16px] text-[#F8FAFC] leading-[1.6] font-normal">{executiveSummary}</p>
          {detailedSummary && detailedSummary !== executiveSummary && (
            <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] leading-[1.6] mt-3 pt-3 border-t border-[#6366F1]/30 font-normal">
              <span className="font-semibold text-[#818CF8]">Detailed Overview: </span>
              {detailedSummary}
            </p>
          )}
        </Card>
      )}

      {/* 2. Key Discussion Points */}
      {keyPoints.length > 0 && (
        <Card className="bg-[#102C4D] border border-[#1D4E78]">
          <div className="flex items-center space-x-2 mb-3 text-[#F8FAFC] font-bold text-[16px] sm:text-[18px]">
            <BookmarkCheck className="w-5 h-5 text-[#3B82F6]" />
            <span>Key Discussion Points ({keyPoints.length})</span>
          </div>
          <ul className="space-y-2.5">
            {keyPoints.map((pt, idx) => (
              <li key={idx} className="flex items-start space-x-2.5 text-[15px] sm:text-[16px] text-[#B8C7DA]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#3B82F6] mt-2 shrink-0" />
                <span className="leading-[1.6]">{pt}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 3. Action Items */}
        <Card className="bg-[#102C4D] border border-[#1D4E78]">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2 text-[#3B82F6] font-bold text-[16px] sm:text-[18px]">
              <CheckSquare className="w-5 h-5" />
              <span>Action Items ({intelligence.action_items?.length || 0})</span>
            </div>
          </div>

          <div className="space-y-2.5">
            {!intelligence.action_items || intelligence.action_items.length === 0 ? (
              <p className="text-[14px] sm:text-[15px] text-[#8FA4BD]">No action items detected.</p>
            ) : (
              intelligence.action_items.map((item) => {
                const isDone = item.status === ActionItemStatus.COMPLETED;
                const displayTitle = item.title || item.description || 'Action Item';
                const displayDesc = item.description && item.description !== item.title ? item.description : null;
                return (
                  <div
                    key={item.id}
                    onClick={() => handleToggleActionItem(item.id, item.status)}
                    className={`flex items-start space-x-3 p-3.5 rounded-xl border transition-all cursor-pointer ${
                      isDone
                        ? 'bg-[#0A1B35] border-[#1D4E78] opacity-60'
                        : 'bg-[#123456] border-[#1D4E78] hover:border-[#3B82F6]'
                    }`}
                  >
                    <div
                      className={`mt-1 w-4 h-4 rounded flex items-center justify-center border transition-colors shrink-0 ${
                        isDone
                          ? 'bg-[#22C55E] border-[#22C55E] text-white'
                          : 'border-[#1D4E78] bg-[#102C4D]'
                      }`}
                    >
                      {isDone && <Check className="w-3 h-3 text-white" />}
                    </div>

                    <div className="flex-1 space-y-1">
                      <p className={`text-[15px] sm:text-[16px] text-[#F8FAFC] font-semibold leading-normal ${isDone ? 'line-through text-[#8FA4BD]' : ''}`}>
                        {displayTitle}
                      </p>
                      {displayDesc && <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] leading-relaxed">{displayDesc}</p>}
                      <div className="flex flex-wrap items-center gap-3 text-[13px] sm:text-[14px] text-[#8FA4BD] pt-1">
                        {item.assignee_name && (
                          <span className="flex items-center space-x-1">
                            <User className="w-3.5 h-3.5 text-[#8FA4BD]" />
                            <span>{item.assignee_name}</span>
                          </span>
                        )}
                        {item.priority && (
                          <span className="px-2 py-0.5 rounded text-[12px] font-bold bg-[#0A1B35] text-[#B8C7DA] border border-[#1D4E78]">
                            {item.priority}
                          </span>
                        )}
                        {item.due_date && (
                          <span className="flex items-center space-x-1">
                            <Clock className="w-3.5 h-3.5 text-[#8FA4BD]" />
                            <span>{new Date(item.due_date).toLocaleDateString()}</span>
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </Card>

        <div className="space-y-6">
          {/* 4. Key Decisions */}
          <Card className="bg-[#102C4D] border border-[#1D4E78]">
            <div className="flex items-center space-x-2 mb-3 text-[#22C55E] font-bold text-[16px] sm:text-[18px]">
              <CheckSquare className="w-5 h-5" />
              <span>Key Decisions ({intelligence.decisions?.length || 0})</span>
            </div>
            <div className="space-y-2.5">
              {!intelligence.decisions || intelligence.decisions.length === 0 ? (
                <p className="text-[14px] sm:text-[15px] text-[#8FA4BD]">No key decisions recorded.</p>
              ) : (
                intelligence.decisions.map((dec) => {
                  const decTitle = dec.title || dec.description || '';
                  return (
                    <div
                      key={dec.id}
                      className="p-3.5 rounded-xl bg-[#123456] border border-[#1D4E78] space-y-1"
                    >
                      <p className="text-[15px] sm:text-[16px] text-[#F8FAFC] font-semibold">{decTitle}</p>
                      {dec.context && <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] leading-relaxed">{dec.context}</p>}
                      {dec.impact && (
                        <p className="text-[13px] text-[#22C55E] font-semibold">Impact: {dec.impact}</p>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </Card>

          {/* 5. Open Questions */}
          <Card className="bg-[#102C4D] border border-[#1D4E78]">
            <div className="flex items-center space-x-2 mb-3 text-[#F59E0B] font-bold text-[16px] sm:text-[18px]">
              <HelpCircle className="w-5 h-5" />
              <span>Open Questions ({intelligence.questions?.length || 0})</span>
            </div>
            <div className="space-y-2.5">
              {!intelligence.questions || intelligence.questions.length === 0 ? (
                <p className="text-[14px] sm:text-[15px] text-[#8FA4BD]">No unresolved questions detected.</p>
              ) : (
                intelligence.questions.map((q) => {
                  const qText = q.question || q.question_text || '';
                  return (
                    <div
                      key={q.id}
                      className="p-3.5 rounded-xl bg-[#123456] border border-[#1D4E78] space-y-1"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-[15px] sm:text-[16px] text-[#F8FAFC] font-semibold">{qText}</p>
                        {q.asked_by_speaker_name && (
                          <span className="text-[13px] text-[#8FA4BD] font-medium shrink-0">{q.asked_by_speaker_name}</span>
                        )}
                      </div>
                      {q.answer && (
                        <p className="text-[14px] text-[#22C55E] font-medium">
                          Answer: {q.answer}
                        </p>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </Card>
        </div>
      </div>

      {/* Additional Structured Sections: 6. Risks, 7. Requirements, 8. Follow-ups */}
      {(risks.length > 0 || requirements.length > 0 || followUps.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-2">
          {risks.length > 0 && (
            <Card className="bg-[#102C4D] border border-[#1D4E78]">
              <div className="flex items-center space-x-2 mb-3 text-[#EF4444] font-bold text-[16px] sm:text-[17px]">
                <AlertTriangle className="w-4.5 h-4.5" />
                <span>Risks & Concerns ({risks.length})</span>
              </div>
              <ul className="space-y-2">
                {risks.map((r, idx) => (
                  <li key={idx} className="text-[14px] sm:text-[15px] text-[#B8C7DA] flex items-start space-x-2">
                    <span className="text-[#EF4444] font-bold">•</span>
                    <span className="leading-[1.6]">{r}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {requirements.length > 0 && (
            <Card className="bg-[#102C4D] border border-[#1D4E78]">
              <div className="flex items-center space-x-2 mb-3 text-[#F8FAFC] font-bold text-[16px] sm:text-[17px]">
                <ListChecks className="w-4.5 h-4.5 text-[#3B82F6]" />
                <span>Requirements & Notes ({requirements.length})</span>
              </div>
              <ul className="space-y-2">
                {requirements.map((req, idx) => (
                  <li key={idx} className="text-[14px] sm:text-[15px] text-[#B8C7DA] flex items-start space-x-2">
                    <span className="text-[#3B82F6] font-bold">•</span>
                    <span className="leading-[1.6]">{req}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {followUps.length > 0 && (
            <Card className="bg-[#102C4D] border border-[#1D4E78]">
              <div className="flex items-center space-x-2 mb-3 text-[#3B82F6] font-bold text-[16px] sm:text-[17px]">
                <Lightbulb className="w-4.5 h-4.5" />
                <span>Follow-up Suggestions ({followUps.length})</span>
              </div>
              <ul className="space-y-2">
                {followUps.map((fu, idx) => (
                  <li key={idx} className="text-[14px] sm:text-[15px] text-[#B8C7DA] flex items-start space-x-2">
                    <span className="text-[#3B82F6] font-bold">•</span>
                    <span className="leading-[1.6]">{fu}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}
    </div>
  );
};
