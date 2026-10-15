import React from 'react';
import { Loader2 } from 'lucide-react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'ai';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  icon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  icon,
  className = '',
  disabled,
  type = 'button',
  ...props
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-semibold transition-all duration-150 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#3B82F6]/40 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer';

  const variants = {
    primary: 'bg-[#2563EB] hover:bg-[#3B82F6] text-[#F8FAFC] shadow-md border border-[#3B82F6]/50 active:bg-[#1D4ED8]',
    secondary: 'bg-[#123456] hover:bg-[#1D4E78] text-[#F8FAFC] border border-[#1D4E78] active:bg-[#102C4D]',
    outline: 'bg-[#102C4D] hover:bg-[#123456] text-[#F8FAFC] border border-[#1D4E78] hover:border-[#3B82F6] shadow-sm',
    ghost: 'bg-transparent hover:bg-[#102C4D] text-[#B8C7DA] hover:text-[#F8FAFC]',
    danger: 'bg-[#EF4444] hover:bg-rose-500 text-white shadow-md border border-rose-500/50 active:bg-rose-700',
    ai: 'bg-[#6366F1] hover:bg-indigo-500 text-white shadow-md border border-indigo-400/50 active:bg-indigo-700',
  };

  const sizes = {
    sm: 'text-[13px] sm:text-[14px] px-3 py-1.5 gap-1.5 font-medium',
    md: 'text-[14px] sm:text-[15px] px-4 py-2 gap-2 font-semibold',
    lg: 'text-[15px] sm:text-[16px] px-5 py-2.5 gap-2.5 font-semibold',
  };

  return (
    <button
      type={type}
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >

      {isLoading ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : icon ? (
        <span className="w-4 h-4">{icon}</span>
      ) : null}
      {children}
    </button>
  );
};
