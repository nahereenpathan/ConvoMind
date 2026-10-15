import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  hover?: boolean;
}

export const Card: React.FC<CardProps> = ({ children, className = '', onClick, hover = false }) => {
  return (
    <div
      onClick={onClick}
      className={`bg-[#102C4D] border border-[#1D4E78] rounded-xl p-5 shadow-[0_4px_20px_rgba(0,0,0,0.3)] ${
        hover ? 'hover:bg-[#123456] hover:border-[#3B82F6] hover:shadow-[0_4px_20px_rgba(37,99,235,0.18)] cursor-pointer transition-all duration-200' : ''
      } ${className}`}
    >
      {children}
    </div>
  );
};
