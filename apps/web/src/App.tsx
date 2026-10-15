import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ProtectedRoute } from './components/layout/ProtectedRoute';
import { AppLayout } from './components/layout/AppLayout';
import { ErrorBoundary } from './components/ui/ErrorBoundary';
import { BackendHealthIndicator } from './components/common/BackendHealthIndicator';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { ForgotPasswordPage } from './pages/ForgotPasswordPage';
import { ResetPasswordPage } from './pages/ResetPasswordPage';
import { DashboardPage } from './pages/DashboardPage';
import { MeetingsListPage } from './pages/MeetingsListPage';
import { CreateMeetingPage } from './pages/CreateMeetingPage';
import { MeetingDetailPage } from './pages/MeetingDetailPage';
import { NativeMeetingRoomPage } from './pages/NativeMeetingRoomPage';
import { TasksPage } from './pages/TasksPage';
import { WorkspacePage } from './pages/WorkspacePage';
import { NotificationsPage } from './pages/NotificationsPage';
import { SettingsPage } from './pages/SettingsPage';
import { BillingPage } from './pages/BillingPage';
import { TrashPage } from './pages/TrashPage';

export const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <BackendHealthIndicator />
        <Routes>
          {/* Public Auth Routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />

          {/* Protected App Routes */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/meetings" element={<MeetingsListPage />} />
              <Route path="/trash" element={<TrashPage />} />
              <Route path="/meetings/new" element={<CreateMeetingPage />} />
              <Route path="/meetings/:id" element={<MeetingDetailPage />} />
              <Route path="/meetings/:id/live" element={<NativeMeetingRoomPage />} />
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/action-items" element={<TasksPage />} />
              <Route path="/workspace" element={<WorkspacePage />} />
              <Route path="/billing" element={<BillingPage />} />
              <Route path="/notifications" element={<NotificationsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Route>

          {/* Fallback Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
};
