import { api } from './client';
import {
  SubscriptionPlanResponse,
  WorkspaceSubscriptionResponse,
  WorkspaceUsageResponse,
  CreateSubscriptionResponse,
  PaymentVerificationRequest,
  PaymentTransactionResponse,
} from '../types';

export const billingApi = {
  getPlans: async (): Promise<SubscriptionPlanResponse[]> => {
    const response = await api.get('/billing/plans');
    return response.data;
  },

  getSubscription: async (workspaceId: string): Promise<WorkspaceSubscriptionResponse> => {
    const response = await api.get('/billing/subscription', {
      params: { workspace_id: workspaceId },
    });
    return response.data;
  },

  getUsage: async (workspaceId: string): Promise<WorkspaceUsageResponse> => {
    const response = await api.get('/billing/usage', {
      params: { workspace_id: workspaceId },
    });
    return response.data;
  },

  createSubscription: async (
    workspaceId: string,
    planCode: string
  ): Promise<CreateSubscriptionResponse> => {
    const response = await api.post('/billing/subscriptions', { plan_code: planCode }, {
      params: { workspace_id: workspaceId },
    });
    return response.data;
  },

  verifyPayment: async (
    workspaceId: string,
    payload: PaymentVerificationRequest
  ): Promise<any> => {
    const response = await api.post('/billing/payments/verify', payload, {
      params: { workspace_id: workspaceId },
    });
    return response.data;
  },

  cancelSubscription: async (
    workspaceId: string
  ): Promise<WorkspaceSubscriptionResponse> => {
    const response = await api.post('/billing/subscriptions/cancel', {}, {
      params: { workspace_id: workspaceId },
    });
    return response.data;
  },

  resumeSubscription: async (
    workspaceId: string
  ): Promise<WorkspaceSubscriptionResponse> => {
    const response = await api.post('/billing/subscriptions/resume', {}, {
      params: { workspace_id: workspaceId },
    });
    return response.data;
  },

  getPaymentHistory: async (
    workspaceId: string
  ): Promise<PaymentTransactionResponse[]> => {
    const response = await api.get('/billing/payments', {
      params: { workspace_id: workspaceId },
    });
    return response.data;
  },
};
