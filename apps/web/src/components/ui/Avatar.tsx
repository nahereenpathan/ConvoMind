import React from 'react';

interface AvatarProps {
  name: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const Avatar: React.FC<AvatarProps> = ({ name, size = 'md', className = '' }) => {
  const getInitials = (n: string) => {
    if (!n) return 'U';
    const parts = n.trim().split(' ');
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    }
    return n.slice(0, 2).toUpperCase();
  };

  const sizes = {
    sm: 'w-7 h-7 text-xs',
    md: 'w-9 h-9 text-sm',
    lg: 'w-12 h-12 text-base font-semibold',
  };

  const colors = [
    'bg-indigo-600 text-indigo-100 border-indigo-400/30',
    'bg-primary-600 text-primary-100 border-primary-400/30',
    'bg-purple-600 text-purple-100 border-purple-400/30',
    'bg-emerald-600 text-emerald-100 border-emerald-400/30',
    'bg-amber-600 text-amber-100 border-amber-400/30',
  ];

  const colorIndex = name ? name.charCodeAt(0) % colors.length : 0;

  return (
    <div
      className={`inline-flex items-center justify-center rounded-full font-medium border border-slate-700/50 shadow-sm ${colors[colorIndex]} ${sizes[size]} ${className}`}
    >
      {getInitials(name)}
    </div>
  );
};
