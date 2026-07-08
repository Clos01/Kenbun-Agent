"use client";

import { MetadataTransformer } from "@/lib/metadataTransformer";
import { METADATA_COMPONENTS, ListCard } from "@/components/MetadataRegistry";
import React, { useEffect, useState, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import { useApiClient } from "@/lib/apiClient";
import { useTenant } from "@/context/TenantContext";
import {
  Search,
  Filter,
  Calendar,
  Mail,
  Phone,
  MapPin,
  Building,
  Clock,
  AlertCircle,
  RefreshCw,
  Tag,
  Database
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Lead, LeadsListSchema } from "@/lib/validation";

// Lead interface is now imported from @/lib/validation

const MOCK_LEADS: Lead[] = [
  {
    id: "d4e5f6a1-b2c3-4d5e-a6f7-112233445566",
    name: "Oakridge Landscaping LLC",
    industry: "Landscaping",
    creation_date: "2026-07-01T10:30:00Z",
    status: "new",
    email: "contact@oakridgelandscape.com",
    phone: "(555) 123-4567",
    address: "884 Wilderness Pkwy, Austin, TX 78701",
    score: 94,
    notes: "Wants a complete commercial xeriscaping redesign for a corporate headquarters campus. Prefers native drought-resistant plants. Budget estimated around $65,000.",
    source: "Google Search (Organic)",
    interaction_history: [
      { date: "2026-07-01T10:32:00Z", agent: "Bayesian-Lead-Ingest", action: "Ingest", summary: "Parsed incoming RFQ form from company website." },
      { date: "2026-07-01T10:35:00Z", agent: "Orchestrator", action: "Verify", summary: "Verified company domain and active commercial license status." }
    ],
    metadata: {
      budget: 65000,
      request_date: "2026-07-01",
      commercial: true,
      location: "Austin, TX",
      collections: ["commercial", "xeriscaping"]
    }
  },
  {
    id: "a1b2c3d4-e5f6-7a8b-9c0d-112233445566",
    name: "Apex Build Group",
    industry: "Construction",
    creation_date: "2026-06-28T08:15:00Z",
    status: "contacted",
    email: "bids@apexbuild.com",
    phone: "(555) 987-6543",
    address: "410 Grand Ave, Suite 200, Denver, CO 80202",
    score: 87,
    notes: "Requires subcontracting bids for concrete framing and foundation work on a new 5-story mixed-use development. Structural drawings available in secure portal.",
    source: "Jira Referral",
    interaction_history: [
      { date: "2026-06-28T08:16:00Z", agent: "Bayesian-Lead-Ingest", action: "Ingest", summary: "Imported bid invitation from external builder exchange." },
      { date: "2026-06-29T09:00:00Z", agent: "Sales-Swarm-1", action: "Email Outbound", summary: "Sent automated introductory credentials package and dynamic pricing model sheet." }
    ],
    metadata: {
      budget: 120000,
      request_date: "2026-06-28",
      commercial: true,
      location: "Denver, CO",
      collections: ["commercial", "foundation"]
    }
  },
  {
    id: "b2c3d4e5-f6a7-8b9c-0d1e-112233445566",
    name: "Flow Right Plumbing Services",
    industry: "Plumbing",
    creation_date: "2026-06-25T14:22:00Z",
    status: "qualified",
    email: "service@flowright.com",
    phone: "(555) 456-7890",
    address: "102 Industrial Way, Charlotte, NC 28202",
    score: 79,
    notes: "Large commercial plumbing system upgrade required for an apartment complex. Heavy pipe lining and main sewer connection replacements.",
    source: "Sovereign Portal",
    interaction_history: [
      { date: "2026-06-25T14:25:00Z", agent: "Bayesian-Lead-Ingest", action: "Ingest", summary: "Detected structural need flags in plumbing forum." },
      { date: "2026-06-26T11:00:00Z", agent: "Auditor-Agent", action: "Audit", summary: "Completed financial background check: Passed (Gold tier)." }
    ],
    metadata: {
      budget: 45000,
      request_date: "2026-06-25",
      commercial: true,
      location: "Charlotte, NC",
      collections: ["commercial", "sewer"]
    }
  },
  {
    id: "c3d4e5f6-a7b8-9c0d-1e2f-112233445566",
    name: "Summit HVAC Solutions",
    industry: "HVAC",
    creation_date: "2026-06-20T09:05:00Z",
    status: "converted",
    email: "info@summithvac.com",
    phone: "(555) 789-0123",
    address: "204 Summit Ridge, Seattle, WA 98101",
    score: 99,
    notes: "Contract signed for ongoing maintenance and smart control retrofitting across 12 branch locations.",
    source: "Warm Outreach Swarm",
    interaction_history: [
      { date: "2026-06-20T09:10:00Z", agent: "Bayesian-Lead-Ingest", action: "Ingest", summary: "Added to database after high-matching response to warm marketing." },
      { date: "2026-06-24T16:45:00Z", agent: "Deal-Close-Swarm", action: "Contract Signed", summary: "System verified signature of Master Service Agreement." }
    ],
    metadata: {
      budget: 35000,
      request_date: "2026-06-20",
      commercial: true,
      location: "Seattle, WA",
      collections: ["commercial", "maintenance"]
    }
  }
];

const CustomMetadataBento = ({ metadata }: { metadata: Lead["metadata"] }) => {
  if (!metadata) return null;

  // Transform raw metadata into normalized visual fields
  const fields = MetadataTransformer.transform(metadata);
  
  // Determine grid alignment context based on siblings
  const hasRecurring = fields.some((f) => f.key === "recurring");

  return (
    <div className="space-y-4">
      <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-tertiary">
        Project Proposal Metadata
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-data">
        <AnimatePresence mode="popLayout">
          {fields.map((field) => {
            const Component = METADATA_COMPONENTS[field.type];
            if (!Component) return null;
            
            if (field.type === "list") {
              return <ListCard key={field.key} field={field} hasRecurring={hasRecurring} />;
            }
            
            return <Component key={field.key} field={field} />;
          })}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default function LeadsPage() {
  const { request } = useApiClient();
  const { tenantId, setTenantId, tenants, currentTenant } = useTenant();

  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [isFallback, setIsFallback] = useState(false);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);

  const [selectedLead, setSelectedLead] = useState<Lead | null>(MOCK_LEADS[0] || null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const loadLeads = useCallback(async () => {
    setLoading(true);
    setErrorDetail(null);
    setIsFallback(false);

    try {
      console.log(`[LEADS] Fetching api/v1/leads with tenant: ${tenantId}`);
      let response = await request("api/v1/leads");

      if (!response.ok) {
        console.log(`[LEADS] api/v1/leads failed (${response.status}). Trying api/backend/leads...`);
        response = await request("api/backend/leads");
      }

      if (response.ok) {
        const data = await response.json();
        const rawList = Array.isArray(data) ? data : (data.leads || []);
        const leadsList = LeadsListSchema.parse(rawList);
        
        if (leadsList.length > 0) {
          setLeads(leadsList);
          setSelectedLead(leadsList[0]);
        } else {
          console.warn("[LEADS] Empty array returned. Using mock data.");
          setLeads(MOCK_LEADS);
          setSelectedLead(MOCK_LEADS[0]);
          setIsFallback(true);
        }
      } else {
        throw new Error(`Server returned status ${response.status}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error("[LEADS] Data fetch failed. Loading mock data fallback.", err);
      setLeads(MOCK_LEADS);
      setSelectedLead(MOCK_LEADS[0]);
      setIsFallback(true);
      setErrorDetail(msg);
    } finally {
      setLoading(false);
    }
  }, [request, tenantId]);

  useEffect(() => {
    // Avoid synchronous state changes inside useEffect by deferring.
    Promise.resolve().then(() => {
      loadLeads();
    });
  }, [loadLeads]);

  const filteredLeads = leads.filter((lead) => {
    const matchesSearch =
      lead.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      lead.industry.toLowerCase().includes(searchQuery.toLowerCase()) ||
      lead.id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "all" || lead.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusColor = (status: Lead["status"]) => {
    switch (status) {
      case "new":
        return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      case "contacted":
        return "bg-yellow-500/10 text-yellow-500 border-yellow-500/20";
      case "qualified":
        return "bg-purple-500/10 text-purple-500 border-purple-500/20";
      case "converted":
        return "bg-emerald-500/10 text-emerald-500 border-emerald-500/20";
      case "lost":
        return "bg-red-500/10 text-red-500 border-red-500/20";
      default:
        return "bg-neutral-500/10 text-neutral-500 border-neutral-500/20";
    }
  };

  return (
    <div className="min-h-screen bg-neutral flex selection:bg-tertiary selection:text-white max-w-[100vw] overflow-x-hidden font-sans text-primary">
      <Sidebar />

      <main className="flex-1 p-0 relative flex flex-col pb-20 lg:pb-0 min-w-0 overflow-x-hidden">
        <div className="grain-overlay opacity-20" />

        {/* Heritage Page Header */}
        <header className="h-20 lg:h-24 border-b border-primary/5 flex items-center justify-between px-6 lg:px-10 bg-card/40 z-20 sticky top-0 backdrop-blur-xl shrink-0">
          <div className="flex items-center gap-4 lg:gap-8">
            <span className="text-[10px] font-black uppercase tracking-widest opacity-30">SYSTEM.LEADS</span>
            <div className="h-6 w-[1px] bg-primary/10" />
            <span className="font-bold text-lg lg:text-xl uppercase tracking-tighter italic">
              Heritage <span className="text-tertiary">Leads Swarm</span>
            </span>
          </div>

          <div className="flex items-center gap-6 lg:gap-10">
            {isFallback && (
              <div className="flex items-center gap-2 bg-[#AF966F]/10 border border-[#AF966F]/20 px-3 py-1.5 rounded-sm">
                <AlertCircle className="w-3.5 h-3.5 text-[#AF966F]" />
                <span className="text-[9px] uppercase font-black tracking-wider text-[#AF966F]">
                  Fallback Mode Active {errorDetail ? `(${errorDetail})` : ""}
                </span>
              </div>
            )}

            <button
              onClick={loadLeads}
              className="p-2 border border-primary/5 bg-card/40 hover:bg-card/80 text-secondary hover:text-primary transition-all duration-300 rounded-sm"
              title="Force reload leads"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-tertiary" : ""}`} />
            </button>
          </div>
        </header>

        {/* Premium Tenant Info Control Panel */}
        <div className="border-b border-primary/5 bg-card/20 px-6 lg:px-10 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4 z-10">
          <div className="flex items-center gap-4">
            <Database className="w-4 h-4 text-tertiary/60" />
            <div className="space-y-0.5">
              <span className="text-[9px] font-black uppercase tracking-[0.2em] opacity-40">Active Tenant Scope</span>
              <div className="flex items-center gap-2 text-xs font-mono font-bold">
                <span className="text-primary">{currentTenant?.name || "Custom Tenant"}</span>
                <span className="text-secondary/40">({tenantId})</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-[9px] uppercase tracking-wider font-bold opacity-50">Select Test Tenant:</span>
            <select
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              className="bg-card border border-primary/10 text-xs py-1.5 px-3 rounded-sm text-primary focus:outline-none focus:ring-1 focus:ring-tertiary cursor-pointer font-bold"
            >
              {tenants.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Main Content Dashboard Grid */}
        <div className="flex-1 flex flex-col lg:flex-row divide-y lg:divide-y-0 lg:divide-x divide-primary/5 relative min-h-0">
          
          {/* LEFT PANEL: Leads Listing */}
          <div className="w-full lg:w-[380px] xl:w-[420px] flex flex-col bg-card/10 shrink-0 min-h-0">
            {/* Search and Filters */}
            <div className="p-4 border-b border-primary/5 space-y-3 bg-card/30">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-secondary/50" />
                <input
                  type="text"
                  placeholder="Search leads name or industry..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-card border border-primary/5 focus:border-tertiary/40 py-2 pl-9 pr-4 text-xs rounded-sm text-primary focus:outline-none focus:ring-1 focus:ring-tertiary/20 placeholder:opacity-40 font-sans"
                />
              </div>

              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-wider text-secondary">
                  <Filter className="w-3 h-3" /> Filter Status
                </div>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-card border border-primary/5 text-[10px] py-1 px-2.5 rounded-sm text-primary focus:outline-none focus:ring-1 focus:ring-tertiary cursor-pointer uppercase font-bold"
                >
                  <option value="all">All Statuses</option>
                  <option value="new">New</option>
                  <option value="contacted">Contacted</option>
                  <option value="qualified">Qualified</option>
                  <option value="converted">Converted</option>
                  <option value="lost">Lost</option>
                </select>
              </div>
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1 bg-card/5">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-20 gap-3">
                  <div className="w-6 h-6 border-2 border-primary/10 border-t-tertiary rounded-full animate-spin" />
                  <span className="text-[10px] font-black uppercase tracking-widest text-secondary">Loading Leads Swarm...</span>
                </div>
              ) : filteredLeads.length === 0 ? (
                <div className="text-center py-20 text-secondary/40 text-xs font-bold uppercase tracking-wider">
                  No Leads Found
                </div>
              ) : (
                filteredLeads.map((lead) => {
                  const isSelected = selectedLead?.id === lead.id;
                  return (
                    <button
                      key={lead.id}
                      onClick={() => setSelectedLead(lead)}
                      className={`w-full text-left p-4 rounded-sm border transition-all duration-300 relative group flex flex-col gap-2.5 ${
                        isSelected
                          ? "bg-card border-tertiary/20 shadow-md shadow-primary/5"
                          : "bg-card/40 border-primary/5 hover:bg-card/85"
                      }`}
                    >
                      {/* Top Row: Name, Score */}
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-0.5">
                          <h3 className="text-xs font-bold tracking-tight text-primary font-sans leading-tight">
                            {lead.name}
                          </h3>
                          <div className="flex items-center gap-1.5">
                            <span className="text-[9px] font-black uppercase tracking-wider text-secondary">
                              {lead.industry}
                            </span>
                          </div>
                        </div>

                        <div className="flex flex-col items-end shrink-0">
                          <span className="text-[8px] font-black uppercase tracking-widest text-secondary/50">Score</span>
                          <span className="text-xs font-black italic tracking-tighter text-tertiary">
                            {lead.score}%
                          </span>
                        </div>
                      </div>

                      {/* Middle Row: Date & Status */}
                      <div className="flex items-center justify-between text-[9px] font-mono text-secondary">
                        <div className="flex items-center gap-1">
                          <Calendar className="w-3 h-3 text-secondary/40" />
                          <span>{new Date(lead.creation_date).toLocaleDateString()}</span>
                        </div>
                        <span className={`px-2 py-0.5 border text-[8px] font-black uppercase tracking-widest rounded-sm ${getStatusColor(lead.status)}`}>
                          {lead.status}
                        </span>
                      </div>

                      {isSelected && (
                        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-8 bg-tertiary" />
                      )}
                    </button>
                  );
                })
              )}
            </div>
          </div>

          {/* RIGHT PANEL: Details Inspector */}
          <div className="flex-1 flex flex-col bg-neutral/20 min-h-0 overflow-y-auto custom-scrollbar p-6 lg:p-10">
            <AnimatePresence mode="wait">
              {selectedLead ? (
                <motion.div
                  key={selectedLead.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.3 }}
                  className="space-y-8 max-w-4xl"
                >
                  {/* Lead Title & Meta */}
                  <div className="border-b border-primary/5 pb-6 space-y-4">
                    <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-[8px] font-mono uppercase tracking-[0.2em] text-secondary">Lead Identifier:</span>
                          <span className="text-[9px] font-mono text-secondary/60">{selectedLead.id}</span>
                        </div>
                        <h1 className="text-2xl lg:text-3xl font-black tracking-tight text-primary font-sans leading-tight uppercase italic">
                          {selectedLead.name}
                        </h1>
                      </div>

                      <div className="flex items-center gap-4">
                        <div className="bg-card border border-primary/5 p-3 rounded-sm text-center shrink-0">
                          <span className="block text-[8px] font-black uppercase tracking-widest text-secondary/50">Lead Score</span>
                          <span className="text-xl font-black italic tracking-tighter text-tertiary">
                            {selectedLead.score}%
                          </span>
                        </div>

                        <div className="bg-card border border-primary/5 p-3 rounded-sm text-center shrink-0">
                          <span className="block text-[8px] font-black uppercase tracking-widest text-secondary/50">Status</span>
                          <span className={`block text-[9px] font-black uppercase tracking-widest mt-1 border px-2 py-0.5 rounded-sm ${getStatusColor(selectedLead.status)}`}>
                            {selectedLead.status}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Two Column details */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    
                    {/* Contact details */}
                    <div className="bg-card border border-primary/5 p-6 rounded-sm space-y-4">
                      <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-tertiary">Contact Protocols</h2>
                      
                      <div className="space-y-3.5">
                        <div className="flex items-center gap-3 text-xs">
                          <Mail className="w-4 h-4 text-secondary/40 shrink-0" />
                          <div className="flex flex-col">
                            <span className="text-[8px] font-black uppercase tracking-widest text-secondary/50">Email Address</span>
                            <a href={`mailto:${selectedLead.email}`} className="text-primary hover:underline font-bold">
                              {selectedLead.email}
                            </a>
                          </div>
                        </div>

                        <div className="flex items-center gap-3 text-xs">
                          <Phone className="w-4 h-4 text-secondary/40 shrink-0" />
                          <div className="flex flex-col">
                            <span className="text-[8px] font-black uppercase tracking-widest text-secondary/50">Contact Phone</span>
                            <span className="text-primary font-bold">{selectedLead.phone}</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-3 text-xs">
                          <MapPin className="w-4 h-4 text-secondary/40 shrink-0" />
                          <div className="flex flex-col">
                            <span className="text-[8px] font-black uppercase tracking-widest text-secondary/50">Address / Location</span>
                            <span className="text-primary font-bold leading-normal">{selectedLead.address}</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Meta details */}
                    <div className="bg-card border border-primary/5 p-6 rounded-sm space-y-4">
                      <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-secondary">System Metadata</h2>
                      
                      <div className="space-y-3.5">
                        <div className="flex items-center gap-3 text-xs">
                          <Building className="w-4 h-4 text-secondary/40 shrink-0" />
                          <div className="flex flex-col">
                            <span className="text-[8px] font-black uppercase tracking-widest text-secondary/50">Industry Segment</span>
                            <span className="text-primary font-bold">{selectedLead.industry}</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-3 text-xs">
                          <Tag className="w-4 h-4 text-secondary/40 shrink-0" />
                          <div className="flex flex-col">
                            <span className="text-[8px] font-black uppercase tracking-widest text-secondary/50">Acquisition Source</span>
                            <span className="text-primary font-bold">{selectedLead.source}</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-3 text-xs">
                          <Clock className="w-4 h-4 text-secondary/40 shrink-0" />
                          <div className="flex flex-col">
                            <span className="text-[8px] font-black uppercase tracking-widest text-secondary/50">Ingestion Timestamp</span>
                            <span className="text-primary font-bold">
                              {new Date(selectedLead.creation_date).toLocaleString()}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                  </div>

                  {/* Custom Metadata Bento Grid Dynamic Renderer */}
                  <CustomMetadataBento metadata={selectedLead.metadata} />

                  {/* Notes / Narrative */}
                  <div className="bg-card border border-primary/5 p-6 rounded-sm space-y-3">
                    <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-secondary">Lead Narrative / Notes</h2>
                    <p className="text-xs text-primary/70 leading-relaxed font-sans font-medium whitespace-pre-line">
                      {selectedLead.notes}
                    </p>
                  </div>

                  {/* Agent Interaction History Timeline */}
                  <div className="bg-card border border-primary/5 p-6 rounded-sm space-y-6">
                    <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-tertiary">Bayesian Swarm Interaction Timeline</h2>
                    
                    <div className="relative border-l border-primary/5 pl-6 ml-3 space-y-6">
                      {selectedLead.interaction_history.map((log, index) => (
                        <div key={index} className="relative group">
                          
                          {/* Timeline dot */}
                          <div className="absolute -left-[30px] top-1.5 w-2 h-2 rounded-full bg-tertiary border border-card group-hover:scale-125 transition-transform" />
                          
                          <div className="space-y-1">
                            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                              <span className="text-[10px] font-mono text-secondary">
                                {new Date(log.date).toLocaleTimeString()}
                              </span>
                              <span className="text-[10px] font-black uppercase tracking-wider text-primary">
                                {log.agent}
                              </span>
                              <span className="text-[8px] font-black uppercase tracking-widest bg-primary/5 border border-primary/5 px-1.5 py-0.5 rounded-sm text-secondary">
                                {log.action}
                              </span>
                            </div>
                            <p className="text-xs text-secondary leading-relaxed font-sans">
                              {log.summary}
                            </p>
                          </div>

                        </div>
                      ))}
                    </div>
                  </div>

                </motion.div>
              ) : (
                <div className="flex-1 flex items-center justify-center text-center py-20 text-secondary/40 text-xs font-bold uppercase tracking-wider">
                  Select a lead from the list to inspect detailed metadata
                </div>
              )}
            </AnimatePresence>
          </div>

        </div>
      </main>
    </div>
  );
}
