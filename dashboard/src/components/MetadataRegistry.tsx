"use client";

import React from "react";
import { motion } from "framer-motion";
import {
  CircleDollarSign,
  Calendar,
  CheckSquare,
  Square,
  Tag,
  MapPin,
  Repeat,
  Database
} from "lucide-react";
import { NormalizedMetadataField } from "@/lib/metadataTransformer";

// ==========================================
// Reusable Card Container Wrapper
// ==========================================
interface ContainerProps {
  label: string;
  icon: React.ReactNode;
  colSpan?: string;
  children: React.ReactNode;
}

export const MetadataCardContainer = ({
  label,
  icon,
  colSpan = "col-span-1",
  children
}: ContainerProps) => {
  return (
    <motion.div
      whileHover={{ scale: 1.01, translateY: -2 }}
      className={`${colSpan} bg-card border border-primary/5 p-5 rounded-sm relative overflow-hidden group flex flex-col justify-between min-h-[120px] transition-all duration-300 shadow-sm`}
    >
      {/* Blueprint premium hover mesh/wash overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-tertiary/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
      
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-black uppercase tracking-wider text-secondary">
          {label}
        </span>
        <div className="text-tertiary group-hover:scale-110 transition-transform duration-300">
          {icon}
        </div>
      </div>
      <div className="mt-4 flex-1 flex flex-col justify-end">
        {children}
      </div>
    </motion.div>
  );
};

// ==========================================
// Type-Specific Components
// ==========================================

export const CurrencyCard = ({ field }: { field: NormalizedMetadataField }) => {
  const value = typeof field.value === "number" ? field.value : parseFloat(String(field.value)) || 0;
  
  const formatted = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  }).format(value);

  // Budget card is highly prioritized and occupies 2 columns by default
  const colSpan = field.key === "budget" ? "md:col-span-2" : "md:col-span-1";

  return (
    <MetadataCardContainer 
      label={field.label} 
      icon={<CircleDollarSign className="w-4.5 h-4.5" />} 
      colSpan={colSpan}
    >
      <span className="text-3xl font-black italic tracking-tighter text-primary">
        {formatted}
      </span>
    </MetadataCardContainer>
  );
};

export const DateCard = ({ field }: { field: NormalizedMetadataField }) => {
  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr + "T00:00:00");
      return date.toLocaleDateString("en-US", {
        month: "long",
        day: "numeric",
        year: "numeric"
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <MetadataCardContainer 
      label={field.label} 
      icon={<Calendar className="w-4.5 h-4.5" />}
    >
      <span className="text-sm font-bold text-primary">
        {formatDate(String(field.value))}
      </span>
    </MetadataCardContainer>
  );
};

export const BooleanCard = ({ field }: { field: NormalizedMetadataField }) => {
  const isTrue = !!field.value;

  const getBooleanText = () => {
    // Custom label override matching leads dashboard requirements
    if (field.key === "commercial") {
      return isTrue ? "Commercial" : "Residential";
    }
    return isTrue ? "Yes" : "No";
  };

  return (
    <MetadataCardContainer 
      label={field.label} 
      icon={isTrue ? <CheckSquare className="w-4.5 h-4.5" /> : <Square className="w-4.5 h-4.5 text-secondary/40" />}
    >
      <div className="flex items-center gap-2">
        <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-0.5 rounded-sm border ${
          isTrue 
            ? "bg-tertiary/10 text-tertiary border-tertiary/20" 
            : "bg-secondary/10 text-secondary border-secondary/20"
        }`}>
          {getBooleanText()}
        </span>
      </div>
    </MetadataCardContainer>
  );
};

export const ListCard = ({ 
  field, 
  hasRecurring 
}: { 
  field: NormalizedMetadataField; 
  hasRecurring?: boolean;
}) => {
  const list = Array.isArray(field.value) ? field.value : [];
  
  // Span 2 columns if no recurring field is present to balance the Bento grid
  const colSpan = hasRecurring ? "md:col-span-1" : "md:col-span-2";

  return (
    <MetadataCardContainer 
      label={field.label} 
      icon={<Tag className="w-4.5 h-4.5" />} 
      colSpan={colSpan}
    >
      <div className="flex flex-wrap gap-1.5 mt-2">
        {list.map((item, idx) => (
          <span
            key={idx}
            className="bg-primary/5 text-primary border border-primary/5 text-[9px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-sm"
          >
            {item}
          </span>
        ))}
      </div>
    </MetadataCardContainer>
  );
};

export const StringCard = ({ field }: { field: NormalizedMetadataField }) => {
  const getIcon = () => {
    switch (field.key) {
      case "location":
        return <MapPin className="w-4.5 h-4.5" />;
      case "recurring":
        return <Repeat className="w-4.5 h-4.5" />;
      default:
        return <Database className="w-4.5 h-4.5" />;
    }
  };

  return (
    <MetadataCardContainer 
      label={field.label} 
      icon={getIcon()}
    >
      <span className="text-sm font-bold text-primary">
        {String(field.value)}
      </span>
    </MetadataCardContainer>
  );
};

// ==========================================
// Component Registry Mapping
// ==========================================

export const METADATA_COMPONENTS: Record<
  NormalizedMetadataField["type"],
  React.ComponentType<{ field: NormalizedMetadataField }>
> = {
  currency: CurrencyCard,
  date: DateCard,
  boolean: BooleanCard,
  list: ListCard,
  string: StringCard,
};
