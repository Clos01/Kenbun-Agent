"use client";

import React, { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export interface DropdownOption {
  value: string;
  label: string;
  icon?: React.ReactNode;
}

interface CustomDropdownProps {
  value: string;
  onChange: (value: string) => void;
  options: DropdownOption[];
  placeholder?: string;
  className?: string;
  id?: string;
  size?: "sm" | "md";
  placement?: "bottom" | "top" | "auto";
}

export default function CustomDropdown({
  value,
  onChange,
  options,
  placeholder = "Select option...",
  className = "",
  id,
  size = "md",
  placement = "bottom"
}: CustomDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedOption = options.find((opt) => opt.value === value);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (val: string) => {
    onChange(val);
    setIsOpen(false);
  };

  const py = size === "sm" ? "py-1 px-2 text-[10px]" : "py-2 px-3 text-xs";

  return (
    <div ref={containerRef} className={`relative inline-block w-full ${className}`} id={id}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        className={`w-full flex items-center justify-between gap-2 bg-card hover:bg-neutral/40 border border-border focus:border-tertiary/60 rounded-lg text-primary font-mono font-medium shadow-sm transition-all cursor-pointer outline-none ${py}`}
      >
        <span className="truncate flex items-center gap-2">
          {selectedOption?.icon}
          <span>{selectedOption ? selectedOption.label : placeholder}</span>
        </span>
        <ChevronDown className={`w-3.5 h-3.5 text-secondary shrink-0 transition-transform duration-200 ${isOpen ? "rotate-180 text-tertiary" : ""}`} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: placement === "top" ? 4 : -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: placement === "top" ? 4 : -4, scale: 0.98 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className={`absolute left-0 right-0 ${
              placement === "top" ? "bottom-full mb-1.5" : "top-full mt-1.5"
            } z-[100] bg-card/98 backdrop-blur-2xl border border-border/80 rounded-xl shadow-[0_15px_30px_rgba(0,0,0,0.4)] overflow-hidden py-1 max-h-60 overflow-y-auto`}
            role="listbox"
          >
            {options.map((opt) => {
              const isSelected = opt.value === value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => handleSelect(opt.value)}
                  className={`w-full text-left flex items-center justify-between gap-2 px-3 py-2 text-xs font-mono transition-colors cursor-pointer ${
                    isSelected
                      ? "bg-tertiary/15 text-tertiary font-bold"
                      : "text-primary hover:bg-neutral/60 hover:text-primary"
                  }`}
                  role="option"
                  aria-selected={isSelected}
                >
                  <span className="truncate flex items-center gap-2">
                    {opt.icon}
                    <span>{opt.label}</span>
                  </span>
                  {isSelected && <Check className="w-3.5 h-3.5 text-tertiary shrink-0" />}
                </button>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
