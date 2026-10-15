import React from 'react';

export interface Tab {
  id: string;
  label: string;
  icon?: React.ReactNode;
  badge?: number | string;
}

interface TabsProps {
  tabs: Tab[];
  activeTab: string;
  onChange: (id: string) => void;
  className?: string;
}

export const Tabs: React.FC<TabsProps> = ({ tabs, activeTab, onChange, className = '' }) => {
  return (
    <div className={`flex border-b border-[#1D4E78] space-x-1 ${className}`}>
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={`flex items-center space-x-2 px-4 py-2.5 text-[14px] sm:text-[15px] font-semibold border-b-2 rounded-t-lg transition-all duration-150 cursor-pointer ${
              isActive
                ? 'border-[#3B82F6] text-[#3B82F6] font-bold bg-[#123456]'
                : 'border-transparent text-[#B8C7DA] hover:text-[#F8FAFC] hover:bg-[#102C4D]'
            }`}
          >
            {tab.icon && <span className="w-4 h-4">{tab.icon}</span>}
            <span>{tab.label}</span>
            {tab.badge !== undefined && (
              <span
                className={`ml-1.5 px-2 py-0.5 text-[12px] rounded-full font-medium ${
                  isActive ? 'bg-[#2563EB]/20 text-[#3B82F6] font-bold border border-[#2563EB]/40' : 'bg-[#123456] text-[#8FA4BD]'
                }`}
              >
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
