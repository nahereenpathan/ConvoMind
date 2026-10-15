import React from 'react';
import { LogOut } from 'lucide-react';
import { useAuthStore } from '../../stores/useAuthStore';
import { NotificationDropdown } from './NotificationDropdown';
import { Avatar } from '../ui/Avatar';
import { useNavigate } from 'react-router-dom';

export const Navbar: React.FC = () => {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="h-16 bg-[#0B2342] border-b border-[#1D4E78] sticky top-0 z-40 px-6 flex items-center justify-between shadow-md">
      <div className="flex items-center space-x-3">
        <span className="text-[14px] sm:text-[15px] text-[#B8C7DA] font-medium">
          Welcome back, <strong className="text-[#F8FAFC] font-bold">{user?.full_name || user?.email}</strong>
        </span>
      </div>

      <div className="flex items-center space-x-4">
        <NotificationDropdown />

        <div className="h-4 w-[1px] bg-[#1D4E78]" />

        <div className="flex items-center space-x-3">
          <Avatar name={user?.full_name || user?.email || 'User'} size="sm" />
          <div className="hidden sm:block text-left">
            <p className="text-[14px] font-semibold text-[#F8FAFC]">{user?.full_name || 'User'}</p>
            <p className="text-[12px] text-[#8FA4BD] truncate max-w-[130px]">{user?.email}</p>
          </div>
          <button
            onClick={handleLogout}
            title="Sign out"
            className="p-2 text-[#8FA4BD] hover:text-[#EF4444] hover:bg-[#102C4D] rounded-lg transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};
