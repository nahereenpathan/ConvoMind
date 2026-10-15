import React, { forwardRef } from 'react';
import { getErrorMessage } from '../../utils/error';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: any;
  helperText?: string;
  icon?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, icon, className = '', id, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

    return (
      <div className="w-full space-y-1.5">
        {label && (
          <label htmlFor={inputId} className="block text-[13px] sm:text-[14px] font-semibold text-[#B8C7DA]">
            {label}
          </label>
        )}
        <div className="relative">
          {icon && (
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#8FA4BD]">
              {icon}
            </div>
          )}
          <input
            id={inputId}
            ref={ref}
            className={`w-full bg-[#123456] border ${
              error
                ? 'border-[#EF4444] focus:border-rose-400 focus:ring-rose-500/20'
                : 'border-[#1D4E78] focus:border-[#3B82F6] focus:ring-[#3B82F6]/20'
            } text-[#F8FAFC] placeholder-[#8FA4BD] text-[14px] sm:text-[15px] rounded-lg ${
              icon ? 'pl-9' : 'pl-3'
            } pr-3 py-2 shadow-sm transition-all duration-150 focus:outline-none focus:ring-2 disabled:bg-[#0A1B35] disabled:text-[#8FA4BD] disabled:cursor-not-allowed ${className}`}
            {...props}
          />
        </div>
        {error ? (
          <p className="text-[12px] sm:text-[13px] text-[#EF4444] font-medium">{getErrorMessage(error)}</p>
        ) : helperText ? (
          <p className="text-[12px] text-[#8FA4BD]">{helperText}</p>
        ) : null}
      </div>
    );
  }
);

Input.displayName = 'Input';
