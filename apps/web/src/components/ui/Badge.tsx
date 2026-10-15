import React from 'react';

export type BadgeVariant = 'default' | 'primary' | 'violet' | 'success' | 'warning' | 'danger' | 'info';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  className = '',
}) => {
  const variantStyles = {
    default: 'bg-[#123456] text-[#B8C7DA] border-[#1D4E78]',
    primary: 'bg-[#2563EB]/20 text-[#3B82F6] border-[#2563EB]/50 font-semibold',
    violet: 'bg-[#6366F1]/20 text-[#818CF8] border-[#6366F1]/50 font-semibold',
    success: 'bg-[#22C55E]/15 text-[#22C55E] border-[#22C55E]/40 font-semibold',
    warning: 'bg-[#F59E0B]/15 text-[#F59E0B] border-[#F59E0B]/40 font-semibold',
    danger: 'bg-[#EF4444]/15 text-[#EF4444] border-[#EF4444]/40 font-semibold',
    info: 'bg-[#22D3EE]/15 text-[#22D3EE] border-[#22D3EE]/40 font-semibold',
  };

  const sizeStyles = {
    sm: 'text-[11px] sm:text-[12px] px-2 py-0.5',
    md: 'text-[12px] sm:text-[13px] px-2.5 py-1',
  };

  return (
    <span
      className={`inline-flex items-center font-semibold border rounded-full ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
    >
      {children}
    </span>
  );
};
