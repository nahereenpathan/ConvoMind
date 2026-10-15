import React, { useEffect } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../../stores/useAuthStore';
import { useWorkspaceStore } from '../../stores/useWorkspaceStore';

export const ProtectedRoute: React.FC = () => {
  const { isAuthenticated, fetchCurrentUser } = useAuthStore();
  const { fetchWorkspaces } = useWorkspaceStore();

  useEffect(() => {
    if (isAuthenticated) {
      fetchCurrentUser();
      fetchWorkspaces();
    }
  }, [isAuthenticated, fetchCurrentUser, fetchWorkspaces]);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
};
