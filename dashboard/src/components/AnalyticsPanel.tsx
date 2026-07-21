"use client";

import React, { useMemo } from "react";
import { motion } from "framer-motion";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { X, CheckCircle2, Clock, AlertCircle } from "lucide-react";

interface Card {
  id: string;
  listId: string;
  name: string;
  description: string;
  position: number;
  isClosed: boolean;
  dueDate?: string;
  listChangedAt?: string;
}

interface List {
  id: string;
  boardId: string;
  name: string;
  position: number;
  type: string;
}

interface AnalyticsPanelProps {
  cards: Card[];
  lists: List[];
  onClose: () => void;
  onOpenCard?: (card: any) => void;
}

const COLORS = ['#F97316', '#3B82F6', '#10B981', '#8B5CF6', '#F43F5E', '#EAB308'];

export default function AnalyticsPanel({ cards, lists, onClose, onOpenCard }: AnalyticsPanelProps) {
  const { chartData, activeTasks, completedTasksCount, totalTasksCount } = useMemo(() => {
    const listMap = new Map<string, List>();
    lists.forEach(l => listMap.set(l.id, l));
    
    const stats: Record<string, number> = {};
    const active: any[] = [];
    let completed = 0;
    
    cards.forEach(card => {
      if (card.isClosed) {
        completed++;
        return;
      }
      
      const list = listMap.get(card.listId);
      const listName = list ? list.name : "Unknown";
      
      const isDoneList = listName.toLowerCase().includes("done") || listName.toLowerCase().includes("complete");
      if (isDoneList) {
        completed++;
      }
      
      stats[listName] = (stats[listName] || 0) + 1;
      
      active.push({
        ...card,
        listName,
        isDone: isDoneList
      });
    });
    
    const chartData = Object.entries(stats).map(([name, value]) => ({ name, value }));
    active.sort((a, b) => {
      if (a.isDone === b.isDone) return 0;
      return a.isDone ? 1 : -1;
    });

    return { 
      chartData, 
      activeTasks: active, 
      completedTasksCount: completed,
      totalTasksCount: cards.length
    };
  }, [cards, lists]);

  const progress = totalTasksCount > 0 ? Math.round((completedTasksCount / totalTasksCount) * 100) : 0;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ type: "spring", damping: 25, stiffness: 300 }}
      className="w-full h-full flex flex-col bg-transparent"
    >
      <div className="flex-1 overflow-y-auto p-4 sm:p-8 flex flex-col gap-6 sm:gap-8 custom-scrollbar items-center">
        <div className="w-full max-w-5xl flex flex-col gap-8">
          
          <div className="flex items-center justify-between pb-6 border-b border-border/40">
            <div>
              <h2 className="text-2xl font-mono font-bold tracking-widest text-primary uppercase drop-shadow-sm">Analytics & Progress</h2>
              <p className="text-sm text-secondary mt-1.5 font-medium">Real-time workflow metrics and insights</p>
            </div>
          </div>
        
        {/* Progress Overview */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-card/70 backdrop-blur-xl rounded-2xl p-6 border border-border shadow-sm relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            <div className="flex items-center gap-2 mb-4 relative z-10">
              <CheckCircle2 className="w-5 h-5 text-emerald-500" />
              <span className="text-xs font-mono font-bold text-secondary uppercase tracking-widest">Completion</span>
            </div>
            <div className="flex items-baseline gap-2 relative z-10">
              <span className="text-5xl font-black text-primary tracking-tighter drop-shadow-sm">{progress}%</span>
            </div>
            <div className="mt-6 h-2 w-full bg-primary/10 rounded-full overflow-hidden relative z-10">
              <motion.div 
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 1.5, delay: 0.2, ease: "easeOut" }}
                className="h-full bg-gradient-to-r from-emerald-400 to-emerald-600 rounded-full"
              />
            </div>
          </div>
          
          <div className="bg-card/70 backdrop-blur-xl rounded-2xl p-6 border border-border shadow-sm relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-orange-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            <div className="flex items-center gap-2 mb-4 relative z-10">
              <Clock className="w-5 h-5 text-orange-500" />
              <span className="text-xs font-mono font-bold text-secondary uppercase tracking-widest">Active</span>
            </div>
            <div className="flex items-baseline gap-2 relative z-10">
              <span className="text-5xl font-black text-primary tracking-tighter drop-shadow-sm">{totalTasksCount - completedTasksCount}</span>
              <span className="text-sm text-secondary font-medium tracking-wide">tasks</span>
            </div>
            <p className="text-xs text-tertiary mt-4 font-medium relative z-10">Remaining in workflow</p>
          </div>
        </div>

        {/* Chart Section */}
        <div className="bg-card/70 backdrop-blur-xl rounded-2xl p-6 border border-border shadow-sm">
          <h3 className="text-xs font-mono font-bold text-secondary uppercase tracking-widest mb-6 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-indigo-500" />
            Task Distribution
          </h3>
          <div className="h-[280px] w-full [&_.recharts-pie-sector]:outline-none [&_.recharts-sector]:outline-none [&_.recharts-layer]:outline-none [&_path]:outline-none">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart style={{ outline: 'none' }}>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                  stroke="none"
                >
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} style={{ outline: 'none' }} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'var(--card)', 
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    fontSize: '11px',
                    fontWeight: 500,
                    boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)'
                  }}
                  itemStyle={{ color: 'var(--primary)' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          
          <div className="flex flex-wrap justify-center gap-6 mt-6">
            {chartData.map((entry, index) => (
              <div key={entry.name} className="flex items-center gap-2 bg-primary/5 px-3 py-1.5 rounded-full border border-border">
                <div className="w-2.5 h-2.5 rounded-full shadow-sm" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
                <span className="text-xs font-medium text-primary tracking-wide">{entry.name} <span className="text-secondary opacity-70">({entry.value})</span></span>
              </div>
            ))}
          </div>
        </div>
        
        {/* Data Table */}
        <div className="mb-8">
          <h3 className="text-xs font-mono font-bold text-secondary uppercase tracking-widest mb-4 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-tertiary" />
            Active Tasks Log
          </h3>
          <div className="border border-border rounded-2xl overflow-hidden bg-card/70 backdrop-blur-xl shadow-sm">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-primary/5 border-b border-border">
                  <th className="px-5 py-4 text-[10px] font-mono font-bold text-secondary uppercase tracking-widest">Task</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {activeTasks.length > 0 ? (
                  activeTasks.slice(0, 15).map(task => (
                    <tr 
                      key={task.id} 
                      className={`hover:bg-primary/5 transition-colors group ${onOpenCard ? 'cursor-pointer' : ''}`}
                      onClick={() => onOpenCard && onOpenCard(task)}
                    >
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3 mb-1">
                          <div className="text-sm font-medium text-primary line-clamp-1 group-hover:text-tertiary transition-colors">{task.name}</div>
                          <span className={`shrink-0 inline-flex items-center justify-center whitespace-nowrap px-2 py-0.5 rounded-full text-[9px] font-bold tracking-widest uppercase shadow-sm ${
                            task.isDone 
                              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.1)]" 
                              : "bg-orange-500/10 text-orange-400 border border-orange-500/20 shadow-[0_0_10px_rgba(249,115,22,0.1)]"
                          }`}>
                            {task.listName}
                          </span>
                        </div>
                        {task.description && <div className="text-xs text-secondary mt-1 line-clamp-1 opacity-70">{task.description}</div>}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="px-5 py-12 text-center text-sm text-secondary italic">
                      No active tasks found in the workflow.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        </div>
      </div>
    </motion.div>
  );
}
