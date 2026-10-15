import React, { useState, useEffect, useCallback } from 'react';
import { CreditCard, Check, ArrowRight, RefreshCw, AlertCircle, ShieldCheck, AlertTriangle } from 'lucide-react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { billingApi } from '../api/billing';
import {
  SubscriptionPlanResponse,
  WorkspaceSubscriptionResponse,
  WorkspaceUsageResponse,
  PaymentTransactionResponse,
} from '../types';


declare global {
  interface Window {
    Razorpay: any;
  }
}

export const BillingPage: React.FC = () => {
  const { activeWorkspace } = useWorkspaceStore();
  const [plans, setPlans] = useState<SubscriptionPlanResponse[]>([]);
  const [subscription, setSubscription] = useState<WorkspaceSubscriptionResponse | null>(null);
  const [usage, setUsage] = useState<WorkspaceUsageResponse | null>(null);
  const [payments, setPayments] = useState<PaymentTransactionResponse[]>([]);
  
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Checkout Modal State
  const [checkoutPlan, setCheckoutPlan] = useState<SubscriptionPlanResponse | null>(null);
  const [showCancelModal, setShowCancelModal] = useState<boolean>(false);

  // Inject Razorpay Checkout JS SDK dynamically
  useEffect(() => {
    if (!document.getElementById('razorpay-sdk')) {
      const script = document.createElement('script');
      script.id = 'razorpay-sdk';
      script.src = 'https://checkout.razorpay.com/v1/checkout.js';
      script.async = true;
      document.body.appendChild(script);
    }
  }, []);

  const loadBillingData = useCallback(async () => {
    if (!activeWorkspace?.id) return;
    setIsLoading(true);
    setError(null);
    try {
      const [plansRes, subRes, usageRes, historyRes] = await Promise.allSettled([
        billingApi.getPlans(),
        billingApi.getSubscription(activeWorkspace.id),
        billingApi.getUsage(activeWorkspace.id),
        billingApi.getPaymentHistory(activeWorkspace.id),
      ]);

      if (plansRes.status === 'fulfilled') setPlans(plansRes.value);
      if (subRes.status === 'fulfilled') setSubscription(subRes.value);
      if (usageRes.status === 'fulfilled') setUsage(usageRes.value);
      if (historyRes.status === 'fulfilled') setPayments(historyRes.value);

      const rejected = [plansRes, subRes, usageRes, historyRes].find(
        (r) => r.status === 'rejected'
      ) as PromiseRejectedResult | undefined;
      
      if (rejected) {
        const err = rejected.reason;
        console.error('Billing fetch partial error:', err);
        // If plans succeeded, don't show full blocking error unless subscription failed fatally
        if (plansRes.status === 'rejected') {
          setError(err?.response?.data?.detail || 'Unable to load billing plans. Please check connection.');
        }
      }
    } catch (err: any) {
      console.error('Failed to load billing details:', err);
      setError('Unable to load billing data. Please check connection.');
    } finally {
      setIsLoading(false);
    }
  }, [activeWorkspace?.id]);


  useEffect(() => {
    loadBillingData();
  }, [loadBillingData]);

  // Launch Razorpay Checkout
  const handleInitiateUpgrade = async (plan: SubscriptionPlanResponse) => {
    if (!activeWorkspace?.id) return;
    setCheckoutPlan(plan);
  };

  const handleExecutePayment = async () => {
    if (!activeWorkspace?.id || !checkoutPlan) return;
    setCheckoutLoading(true);
    setActionMessage('Connecting to Razorpay checkout gateway...');
    try {
      const checkoutData = await billingApi.createSubscription(activeWorkspace.id, checkoutPlan.code);
      setCheckoutPlan(null);

      // If FREE plan
      if (checkoutData.plan_code === 'FREE') {
        setActionMessage('Workspace plan updated to Starter Tier.');
        await loadBillingData();
        setCheckoutLoading(false);
        setTimeout(() => setActionMessage(null), 4000);
        return;
      }

      // Configure Razorpay SDK options
      const options = {
        key: checkoutData.razorpay_key_id,
        subscription_id: checkoutData.razorpay_subscription_id,
        name: 'ConvoMind SaaS',
        description: `Upgrade to ${checkoutData.plan_name}`,
        image: 'https://cdn-icons-png.flaticon.com/512/4712/4712109.png',
        handler: async (response: any) => {
          setActionMessage('Payment received! Verifying signature with ConvoMind backend...');
          try {
            await billingApi.verifyPayment(activeWorkspace.id, {
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_subscription_id: response.razorpay_subscription_id,
              razorpay_signature: response.razorpay_signature,
            });
            setActionMessage('Payment verified successfully! Subscription active.');
            await loadBillingData();
          } catch (vErr: any) {
            console.error('Payment verification failed:', vErr);
            setError(vErr?.response?.data?.detail || 'Payment verification failed.');
          } finally {
            setCheckoutLoading(false);
            setTimeout(() => setActionMessage(null), 5000);
          }
        },
        modal: {
          ondismiss: () => {
            setCheckoutLoading(false);
            setActionMessage(null);
          },
        },
        prefill: {
          name: activeWorkspace.name,
        },
        theme: {
          color: '#2563EB',
        },
      };

      if (window.Razorpay) {
        const rzp = new window.Razorpay(options);
        rzp.open();
      } else {
        setError('Razorpay Checkout SDK is loading. Please try again in a moment.');
        setCheckoutLoading(false);
      }
    } catch (err: any) {
      console.error('Error starting subscription checkout:', err);
      setError(err?.response?.data?.detail || 'Failed to initiate checkout.');
      setCheckoutLoading(false);
      setActionMessage(null);
    }
  };

  const handleCancelSubscription = async () => {
    if (!activeWorkspace?.id) return;
    try {
      await billingApi.cancelSubscription(activeWorkspace.id);
      setShowCancelModal(false);
      setActionMessage('Subscription scheduled for cancellation at period end.');
      await loadBillingData();
      setTimeout(() => setActionMessage(null), 5000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to cancel subscription.');
    }
  };

  const handleResumeSubscription = async () => {
    if (!activeWorkspace?.id) return;
    try {
      await billingApi.resumeSubscription(activeWorkspace.id);
      setActionMessage('Subscription resumed successfully.');
      await loadBillingData();
      setTimeout(() => setActionMessage(null), 5000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to resume subscription.');
    }
  };

  const formatPrice = (amountPaise: number) => {
    if (amountPaise === 0) return '₹0';
    return `₹${(amountPaise / 100).toLocaleString('en-IN')}`;
  };

  const currentPlanCode = subscription?.plan?.code || 'FREE';

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-fade-in pb-12 text-[#F8FAFC]">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-5 bg-[#102C4D] p-6 sm:p-7 rounded-2xl border border-[#1D4E78] shadow-xl bg-gradient-to-r from-[#102C4D] via-[#123456] to-[#102C4D]">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-[26px] sm:text-[30px] font-bold text-[#F8FAFC]">Billing & Subscriptions</h1>
            <Badge variant={currentPlanCode === 'PRO' ? 'primary' : currentPlanCode === 'ENTERPRISE' ? 'success' : 'info'}>
              {subscription?.plan?.name || 'Starter Tier'}
            </Badge>
            {subscription?.status === 'ACTIVE' && (
              <span className="flex items-center text-xs font-semibold text-[#22C55E] bg-[#166534]/30 px-2.5 py-1 rounded-full border border-[#22C55E]/30">
                <span className="w-2 h-2 rounded-full bg-[#22C55E] mr-1.5 animate-pulse" /> Active
              </span>
            )}
          </div>
          <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] mt-1.5 leading-relaxed">
            Manage subscription plans, usage quotas, and payments for{' '}
            <strong className="text-[#F8FAFC]">{activeWorkspace?.name || 'your workspace'}</strong>.
          </p>
        </div>

        <div className="flex items-center space-x-3 shrink-0">
          <Button variant="outline" size="sm" icon={<RefreshCw className={isLoading ? 'animate-spin' : ''} />} onClick={loadBillingData}>
            Refresh
          </Button>
          {subscription?.cancel_at_period_end ? (
            <Button variant="secondary" size="sm" onClick={handleResumeSubscription}>
              Resume Plan
            </Button>
          ) : currentPlanCode !== 'FREE' ? (
            <Button variant="danger" size="sm" onClick={() => setShowCancelModal(true)}>
              Cancel Plan
            </Button>
          ) : (
            <Button variant="outline" size="sm" icon={<CreditCard />}>
              Manage Payment Method
            </Button>
          )}
        </div>
      </div>

      {/* Action / Error Banner */}
      {actionMessage && (
        <div className="flex items-center space-x-3 bg-[#1E3A8A]/50 border border-[#3B82F6] p-4 rounded-xl text-[#93C5FD]">
          <ShieldCheck className="w-5 h-5 flex-shrink-0" />
          <span className="text-sm font-medium">{actionMessage}</span>
        </div>
      )}

      {error && (
        <div className="flex items-center space-x-3 bg-[#7F1D1D]/50 border border-[#EF4444] p-4 rounded-xl text-[#FCA5A5]">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span className="text-sm font-medium">{error}</span>
        </div>
      )}

      {/* Cancellation Notice if Pending */}
      {subscription?.cancel_at_period_end && (
        <div className="flex items-center justify-between bg-[#451A03]/60 border border-[#F59E0B] p-4 rounded-xl text-[#FDE68A]">
          <div className="flex items-center space-x-3">
            <AlertTriangle className="w-5 h-5 text-[#F59E0B]" />
            <span className="text-sm font-medium">
              Your {subscription.plan.name} subscription will remain active until period end and will not renew.
            </span>
          </div>
          <Button variant="outline" size="sm" onClick={handleResumeSubscription}>
            Keep Subscription
          </Button>
        </div>
      )}

      {/* Usage Meter Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <Card className="space-y-3 bg-[#102C4D] border border-[#1D4E78]">
          <div className="flex items-center justify-between">
            <span className="text-[13px] sm:text-[14px] font-semibold text-[#B8C7DA]">Transcribed Hours</span>
            <span className="text-[13px] sm:text-[14px] font-bold text-[#3B82F6]">
              {usage?.transcribed_hours || 0} / {usage?.max_transcription_hours || 5} hrs
            </span>
          </div>
          <div className="w-full bg-[#0A1B35] rounded-full h-2 overflow-hidden border border-[#1D4E78]">
            <div
              className={`h-2 rounded-full transition-all ${
                (usage?.transcription_percentage || 0) >= 90 ? 'bg-[#EF4444]' : 'bg-[#2563EB]'
              }`}
              style={{ width: `${usage?.transcription_percentage || 0}%` }}
            />
          </div>
          <p className="text-[12px] text-[#8FA4BD]">
            {(usage?.transcription_percentage || 0)}% of plan limit used
          </p>
        </Card>

        <Card className="space-y-3 bg-[#102C4D] border border-[#1D4E78]">
          <div className="flex items-center justify-between">
            <span className="text-[13px] sm:text-[14px] font-semibold text-[#B8C7DA]">RAG AI Queries</span>
            <span className="text-[13px] sm:text-[14px] font-bold text-[#22C55E]">
              {(usage?.rag_queries || 0).toLocaleString()} / {(usage?.max_rag_queries || 100).toLocaleString()}
            </span>
          </div>
          <div className="w-full bg-[#0A1B35] rounded-full h-2 overflow-hidden border border-[#1D4E78]">
            <div
              className={`h-2 rounded-full transition-all ${
                (usage?.rag_percentage || 0) >= 90 ? 'bg-[#EF4444]' : 'bg-[#22C55E]'
              }`}
              style={{ width: `${usage?.rag_percentage || 0}%` }}
            />
          </div>
          <p className="text-[12px] text-[#8FA4BD]">
            {(usage?.rag_percentage || 0)}% of monthly quota used
          </p>
        </Card>

        <Card className="space-y-3 bg-[#102C4D] border border-[#1D4E78]">
          <div className="flex items-center justify-between">
            <span className="text-[13px] sm:text-[14px] font-semibold text-[#B8C7DA]">Workspace Members</span>
            <span className="text-[13px] sm:text-[14px] font-bold text-[#3B82F6]">
              {usage?.members_count || 1} / {usage?.max_members || 2} seats
            </span>
          </div>
          <div className="w-full bg-[#0A1B35] rounded-full h-2 overflow-hidden border border-[#1D4E78]">
            <div
              className="bg-[#3B82F6] h-2 rounded-full transition-all"
              style={{ width: `${usage?.members_percentage || 0}%` }}
            />
          </div>
          <p className="text-[12px] text-[#8FA4BD]">
            {(usage?.max_members || 2) - (usage?.members_count || 1)} seats available in plan
          </p>
        </Card>
      </div>

      {/* Plans Section */}
      <div className="space-y-4">
        <div>
          <h2 className="text-[20px] sm:text-[24px] font-bold text-[#F8FAFC]">Select SaaS Tier</h2>
          <p className="text-[14px] text-[#B8C7DA] mt-0.5">
            Transparent INR pricing backed by Razorpay secure subscription engine.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {plans.map((plan) => {
            const isCurrent = currentPlanCode === plan.code;
            const isPopular = plan.code === 'PRO';

            return (
              <Card
                key={plan.id}
                className={`flex flex-col justify-between space-y-6 relative transition-all bg-[#102C4D] ${
                  isPopular
                    ? 'border-2 border-[#3B82F6] shadow-xl'
                    : isCurrent
                    ? 'border-2 border-[#22C55E]'
                    : 'border border-[#1D4E78]'
                }`}
              >
                {isPopular && (
                  <div className="absolute -top-3 right-4 bg-[#2563EB] text-white text-[11px] font-bold uppercase tracking-wider px-3 py-0.5 rounded-full shadow-sm">
                    Most Popular
                  </div>
                )}

                <div className="space-y-4">
                  <div>
                    <h3 className="text-[18px] sm:text-[20px] font-bold text-[#F8FAFC]">{plan.name}</h3>
                    <p className="text-[13px] sm:text-[14px] text-[#B8C7DA] mt-1 min-h-[32px] leading-relaxed">
                      {plan.description}
                    </p>
                  </div>

                  <div className="flex items-baseline space-x-1">
                    <span className="text-3xl sm:text-4xl font-extrabold text-[#F8FAFC]">
                      {formatPrice(plan.amount)}
                    </span>
                    <span className="text-[13px] sm:text-[14px] text-[#8FA4BD] font-medium">
                      / {plan.billing_interval}
                    </span>
                  </div>

                  <div className="pt-2 border-t border-[#1D4E78] space-y-2.5">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8FA4BD]">
                      Plan Quotas & Entitlements:
                    </span>
                    <div className="flex items-start space-x-2 text-[13px] text-[#B8C7DA]">
                      <Check className="w-4 h-4 text-[#22C55E] flex-shrink-0 mt-0.5" />
                      <span>{plan.max_transcription_hours} Transcribed Hours / month</span>
                    </div>
                    <div className="flex items-start space-x-2 text-[13px] text-[#B8C7DA]">
                      <Check className="w-4 h-4 text-[#22C55E] flex-shrink-0 mt-0.5" />
                      <span>{plan.max_rag_queries.toLocaleString()} RAG AI Queries</span>
                    </div>
                    <div className="flex items-start space-x-2 text-[13px] text-[#B8C7DA]">
                      <Check className="w-4 h-4 text-[#22C55E] flex-shrink-0 mt-0.5" />
                      <span>Up to {plan.max_members} Workspace Members</span>
                    </div>
                    <div className="flex items-start space-x-2 text-[13px] text-[#B8C7DA]">
                      <Check className="w-4 h-4 text-[#22C55E] flex-shrink-0 mt-0.5" />
                      <span>Instant AI Summary & Diarization</span>
                    </div>
                  </div>
                </div>

                <div className="pt-4">
                  {isCurrent ? (
                    <Button variant="outline" className="w-full border-[#22C55E]/50 text-[#22C55E]" disabled>
                      Current Active Plan
                    </Button>
                  ) : (
                    <Button
                      variant={isPopular ? 'primary' : 'outline'}
                      className="w-full"
                      icon={<ArrowRight />}
                      disabled={checkoutLoading}
                      onClick={() => handleInitiateUpgrade(plan)}
                    >
                      {plan.amount > (subscription?.plan?.amount || 0) ? 'Upgrade Plan' : 'Select Plan'}
                    </Button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Payment History Table */}
      <div className="space-y-4 pt-4">
        <div>
          <h2 className="text-[20px] font-bold text-[#F8FAFC]">Billing & Payment History</h2>
          <p className="text-[14px] text-[#B8C7DA] mt-0.5">
            Verified transaction logs and Razorpay payment identifiers.
          </p>
        </div>

        <Card className="bg-[#102C4D] border border-[#1D4E78] overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#0A1B35] border-b border-[#1D4E78] text-[12px] uppercase tracking-wider text-[#8FA4BD]">
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Description</th>
                  <th className="py-3 px-4">Amount</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Payment ID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1D4E78] text-[13px]">
                {payments.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-[#8FA4BD]">
                      No billing transactions recorded yet for this workspace.
                    </td>
                  </tr>
                ) : (
                  payments.map((tx) => (
                    <tr key={tx.id} className="hover:bg-[#123456]/50 transition-colors text-[#B8C7DA]">
                      <td className="py-3 px-4">{new Date(tx.created_at).toLocaleDateString('en-IN')}</td>
                      <td className="py-3 px-4 font-medium text-[#F8FAFC]">ConvoMind Subscription</td>
                      <td className="py-3 px-4 font-bold text-[#F8FAFC]">{formatPrice(tx.amount)}</td>
                      <td className="py-3 px-4">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-[#166534]/40 text-[#22C55E]">
                          {tx.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-xs text-[#8FA4BD]">
                        {tx.razorpay_payment_id || 'N/A'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* Checkout Plan Summary Modal */}
      {checkoutPlan && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#102C4D] border border-[#1D4E78] rounded-2xl p-6 max-w-md w-full space-y-5 text-[#F8FAFC] shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#1D4E78] pb-3">
              <h3 className="text-xl font-bold">Plan Checkout Summary</h3>
              <button
                onClick={() => setCheckoutPlan(null)}
                className="text-[#8FA4BD] hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-sm text-[#B8C7DA]">
              <div className="flex justify-between">
                <span>Selected Plan:</span>
                <strong className="text-white">{checkoutPlan.name}</strong>
              </div>
              <div className="flex justify-between">
                <span>Billing Frequency:</span>
                <strong className="text-white">Monthly Recurring</strong>
              </div>
              <div className="flex justify-between">
                <span>Total Payable:</span>
                <strong className="text-xl font-bold text-[#3B82F6]">
                  {formatPrice(checkoutPlan.amount)} / mo
                </strong>
              </div>
              <div className="bg-[#0A1B35] p-3 rounded-lg border border-[#1D4E78] text-xs text-[#8FA4BD] space-y-1">
                <p>• Secured via Razorpay Subscription Gateway</p>
                <p>• Taxes and GST calculated as per compliance rules</p>
                <p>• Features instantly activated upon server verification</p>
              </div>
            </div>

            <div className="flex justify-end space-x-3 pt-2">
              <Button variant="outline" onClick={() => setCheckoutPlan(null)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleExecutePayment}
                disabled={checkoutLoading}
                icon={<CreditCard />}
              >
                {checkoutLoading ? 'Processing...' : 'Proceed to Razorpay Payment'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Cancellation Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#102C4D] border border-[#1D4E78] rounded-2xl p-6 max-w-md w-full space-y-5 text-[#F8FAFC] shadow-2xl">
            <h3 className="text-xl font-bold text-[#EF4444]">Cancel Subscription</h3>
            <p className="text-sm text-[#B8C7DA]">
              Are you sure you want to cancel your workspace subscription? Your plan will remain active until the end of the current billing cycle.
            </p>
            <div className="flex justify-end space-x-3 pt-2">
              <Button variant="outline" onClick={() => setShowCancelModal(false)}>
                Keep Subscription
              </Button>
              <Button variant="danger" onClick={handleCancelSubscription}>
                Confirm Cancellation
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
