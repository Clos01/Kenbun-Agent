// HMR Refresh Trigger: Whitish Header Theme Updated
import React, { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { Download, FileText, Loader2, RotateCcw, Database } from "lucide-react";
import dynamic from "next/dynamic";
import { useReactToPrint } from "react-to-print";
import "react-quill-new/dist/quill.snow.css";
import { tenantFetch } from "../lib/tenantFetch";
import { CONFIG } from "../lib/config";

const API_BASE = CONFIG.API_BASE;

// Dynamic import with SSR disabled for Quill editor
const ReactQuill = dynamic(() => import("react-quill-new"), { ssr: false });

const getClaudeCorpsSOW = () => `
    <h1>Statement of Work &amp; Project Recap: Claude Corps Fellowship</h1>
    <p><strong>Client:</strong> Riverbend Food Alliance</p>
    <p><strong>Date:</strong> ${new Date().toLocaleDateString()}</p>
    
    <h2>1. Overall Objective</h2>
    <p>Act as the new AI Fellow at Riverbend Food Alliance to automate inbox triage, audit quarterly board data, design a volunteer confirmation architecture, and calculate the ROI of AI automation.</p>

    <h2>2. Task Breakdown &amp; Defenses</h2>
    
    <h3>2a. The Triage Prompt (Email 1 &mdash; Marcus)</h3>
    <ul>
      <li><strong>Action Taken:</strong> Wrote an AI prompt for Claude 3 Haiku to categorize incoming emails at <code>donate@</code>.</li>
      <li><strong>The Logic (Security Pivot):</strong> 
        <ul>
          <li>Forced the AI to return <strong>strict JSON</strong> (using enums) rather than free-text responses to prevent hallucinations.</li>
          <li>Hardcoded a rule: <strong><code>draft: null</code> for Major Donors</strong>. This ensures the AI cannot make unauthorized commitments to VIPs, keeping a human (Marcus) firmly in the loop for high-liability relationships.</li>
          <li>Previous AI was hallucinating facts (inventing warehouse hours) and making unauthorized commitments on behalf of the Director.</li>
        </ul>
      </li>
      <li><strong>Key Files:</strong> <code>triage_prompt.md</code>, <code>failure_examples.md</code>, <code>corrections.csv</code></li>
    </ul>

    <h3>2b. The Data Audit (Email 2 &mdash; Diane)</h3>
    <ul>
      <li><strong>Action Taken:</strong> Fact-checked Diane's draft Q1 Board Memo against raw Excel exports.</li>
      <li><strong>The Logic (Data Verification):</strong>
        <ul>
          <li>Didn't blindly trust the AI's surface-level summary. Forced a deep merge of the Excel sheets and used cross-model checks.</li>
          <li><strong>The "T-99" Catch:</strong> Used <code>cmd+f</code> cross-referencing to find a dummy test truck (<code>T-99</code>) hiding ~47,000 lbs of fake weight that would have severely skewed the final report.</li>
          <li>Cleaned up spelling duplicates (e.g., 'Mt Zion' vs 'Mt. Zion') that were causing false 'crisis' flags.</li>
          <li>Corrected the county averages table and the Ellis County story.</li>
        </ul>
      </li>
      <li><strong>Key Files:</strong> <code>draft_memo.md</code>, <code>distribution_log_q1.csv/.xlsx</code>, <code>partner_agencies.csv/.xlsx</code>, <code>memo_corrected.md</code></li>
    </ul>

    <h3>2c. The Volunteer Architecture (Email 3 &mdash; Priya)</h3>
    <ul>
      <li><strong>Action Taken:</strong> Sketched a volunteer confirmation flowchart in HTML.</li>
      <li><strong>The Logic (Sovereign &amp; Secure Design):</strong>
        <ul>
          <li><strong>No CDNs:</strong> Explicitly avoided external CDNs (like Mermaid.js) so the HTML would load reliably offline.</li>
          <li><strong>Sovereign Stack / MCP:</strong> Integrated <strong>MCP (Model Context Protocol)</strong> with a local database stack (PostgreSQL, n8n). This allows the AI to read/write securely to a local database without human copy-pasting.</li>
          <li><strong>Exception Handling:</strong> Implemented a &lsquo;Monday Verification Check&rsquo; to keep a human in the loop for edge cases.</li>
        </ul>
      </li>
      <li><strong>Key Files:</strong> <code>architecture.html</code>, <code>handbook.md</code></li>
    </ul>

    <h3>2d. The Budget Math (Email 4 &mdash; Marcus)</h3>
    <ul>
      <li><strong>Action Taken:</strong> Calculated the monthly API costs for triaging 1,200-1,800 emails/month.</li>
      <li><strong>The Logic (ROI Calculation):</strong>
        <ul>
          <li>Pulled the peak volume of 1,800 emails/month from the team handbook.</li>
          <li>Estimated ~1,500 tokens per email on Claude Haiku &mdash; worst-case cost: under <strong>$5/month</strong>.</li>
          <li>Yields a massive <strong>$10,000+ ROI</strong> when comparing to the human hours saved.</li>
        </ul>
      </li>
      <li><strong>Key Files:</strong> <code>handbook.md</code></li>
    </ul>

    <h2>3. Core Interview Themes to Remember</h2>
    <ul>
      <li><strong>Speed vs. Accuracy:</strong> &ldquo;I use AI to accelerate the initial heavy lifting, but I rely on human verification and cross-model checks for critical constraints.&rdquo;</li>
      <li><strong>Risk-Based Auditing:</strong> &ldquo;I lock down the AI&rsquo;s boundaries using strict JSON and human-in-the-loop rules for high-liability tasks.&rdquo;</li>
      <li><strong>Data Sovereignty:</strong> &ldquo;I prioritize offline reliability and secure local data pipelines (MCP + Local Postgres) over cloud-dependent SaaS.&rdquo;</li>
    </ul>

    <h2>4. Live Curveball Preparation</h2>
    <ul>
      <li><strong>Prompt Adjustment:</strong> &ldquo;Marcus wants to add a new category for Disaster Relief.&rdquo; &mdash; Add <code>disaster_relief</code> to the JSON enum, add routing rule to Diane, done in 10 seconds.</li>
      <li><strong>Data Pivot:</strong> &ldquo;Diane wants median instead of average for Ellis County.&rdquo; &mdash; Open a Python script, run <code>df.median()</code> on the filtered data.</li>
      <li><strong>Architecture Expansion:</strong> &ldquo;Priya wants email fallback if SMS fails.&rdquo; &mdash; Add an error-handler branch in n8n that triggers an email node on SMS failure.</li>
    </ul>
`;

const getNeverMissSOW = () => `
    <h1>Statement of Work (SOW)</h1>
    <p><strong>Client:</strong> NeverMiss.ai<br/>
    <strong>Contact:</strong> Adrian Rodriguez (adrian@snappicfix.com)<br/>
    <strong>Date:</strong> ${new Date().toLocaleDateString()}</p>
    
    <h2>1. Project Overview &amp; Architecture Refinement</h2>
    <p>NeverMiss.ai requires a <strong>Self-Improving Fleet Management System</strong> for its ElevenLabs voice agents. The goal is to monitor the performance of all deployed agents from a single pane of glass, automatically evaluate every call, ingest client feedback when an agent makes a mistake, and dynamically suggest improved prompt instructions.</p>
    
    <p><strong>Key Security &amp; Workflow Refinements (Jul 23 Update):</strong></p>
    <ul>
      <li><strong>Webhook-Based Ingestion (Zero Shared Account API Keys):</strong> To preserve security, NeverMiss.ai will stream call transcripts and native post-call evaluation events directly to our n8n Webhook Pipeline (<code>https://n8n.rivasautomations.com/webhook/...</code>), avoiding the need to share raw account API keys for transcript extraction.</li>
      <li><strong>Human-in-the-Loop (HITL) Gatekeeper:</strong> When ElevenLabs native post-call evals or client feedback flag a call failure, our AI Evaluation Engine analyzes the transcript, drafts a targeted prompt revision, and presents it to the developer/admin via the Fleet Dashboard or email. Once approved via one-click HITL verification, the update is pushed directly back to the ElevenLabs Agent API.</li>
    </ul>

    <h2>2. Scope of Work</h2>
    <ul>
      <li><strong>Automated Webhook &amp; Evaluation Pipeline (Self-Reflection):</strong> Setting up a secure n8n webhook listener that ingests 100% of ElevenLabs post-call events and evaluates transcript performance against custom quality rubrics.</li>
      <li><strong>Dynamic Agent Self-Correction with HITL Approval:</strong> When an agent fails an evaluation or receives negative client feedback, an LLM automatically diagnoses the failure mode, drafts improved system instructions, and generates a one-click Human-in-the-Loop Approval Action. Upon human approval, the updated instructions are pushed directly to the ElevenLabs Agent Update API to correct future agent behavior.</li>
      <li><strong>Fleet Monitoring Dashboard:</strong> Designing a single-pane-of-glass analytics dashboard to monitor live call telemetry, historical evaluation metrics, agent failure flags, and the HITL prompt revision queue across the company.</li>
    </ul>
    
    <h2>3. Deliverables</h2>
    <ol>
      <li><strong>Fleet Monitoring &amp; HITL Dashboard</strong> (Built with Next.js 16 + Tailwind CSS)</li>
      <li><strong>Self-Improving Evaluation &amp; ElevenLabs Update Pipeline</strong> (n8n + FastMCP + ElevenLabs API Integration)</li>
      <li><strong>Client Feedback Ingestion Portal</strong> (Interface for logging custom rules &amp; agent corrections)</li>
    </ol>
    
    <h2>4. Architecture &amp; Technology Stack</h2>
    <ul>
      <li><strong>Workflow Automation (n8n on P330 / Cloudflare Tunnel):</strong> Routes post-call webhooks from ElevenLabs into n8n for rapid parsing, AI evaluation (via Gemini 2.0), and database storage without backend overhead.</li>
      <li><strong>Database (<a href="https://azure.microsoft.com/en-us/products/postgresql" target="_blank" rel="noopener noreferrer">Azure Database for PostgreSQL</a>):</strong> A fully managed <a href="https://azure.microsoft.com/en-us/products/postgresql" target="_blank" rel="noopener noreferrer">Azure Database for PostgreSQL Flexible Server</a> (P4 Burstable Tier, 32GB with <code>pgvector</code> extension) will securely store structured call transcripts, evaluation metadata, and prompt revision histories. Billed directly under NeverMiss.ai's corporate Azure account.</li>
      <li><strong>Real-Time Streaming (SSE):</strong> Live call data is pushed directly to the Next.js dashboard, creating a real-time, word-for-word typing effect.</li>
    </ul>
    
    <h2>5. Timeline &amp; Phases</h2>
    <ul>
      <li><strong>Phase 1 (Weeks 1-8):</strong> Core development and monitoring. Building n8n webhook pipelines, establishing Azure PostgreSQL schema, building the Next.js Fleet Dashboard, and implementing the Human-in-the-Loop (HITL) manual approval gate before prompt updates are pushed to ElevenLabs.</li>
      <li><strong>Future Phases (TBD):</strong> Autonomous prompt updates (bypassing manual HITL after validation), prompt injection security monitoring, and advanced sentiment analytics.</li>
    </ul>
    
    <h2>6. Payment Terms</h2>
    <ul>
      <li><strong>Rate:</strong> $24/hour</li>
      <li><strong>Estimated Hours:</strong> Minimum 10 hours per week</li>
      <li><strong>Invoicing Frequency:</strong> Weekly</li>
    </ul>
    
    <h2>7. Client Responsibilities &amp; Security Provisioning</h2>
    <p>To ensure security and compliance, the client agrees to provision access using role-based invites rather than shared passwords. The following access is required before development begins:</p>
    <ul>
      <li><strong>Developer/Admin Invites:</strong> Role-based access to the ElevenLabs workspace.</li>
      <li><strong>Azure Database Provisioning:</strong> Providing the connection string URL for <a href="https://azure.microsoft.com/en-us/products/postgresql" target="_blank" rel="noopener noreferrer">Azure Database for PostgreSQL</a> provisioned under NeverMiss.ai's corporate Azure subscription.</li>
      <li><strong>Sandbox Environment &amp; Testing:</strong> Dedicated test account and blank Google Calendar / Cal.com link, separate ElevenLabs test agent and phone number, and disabled customer SMS/email reminders.</li>
      <li><strong>In-Office Collaboration:</strong> Bi-weekly in-person whiteboard alignment sessions combined with remote flexibility for off-hours development.</li>
    </ul>
    
    <h2>8. Data Security &amp; Compliance</h2>
    <p>Given the handling of voice recordings and transcripts, the following security measures will be implemented:</p>
    <ul>
      <li><strong>Data Encryption:</strong> All call recordings, transcripts, and PII will be encrypted at rest (AES-256) and in transit (TLS 1.3).</li>
      <li><strong>Secret Management:</strong> Production API keys and database credentials will be stored exclusively in AWS Secrets Manager or Azure Key Vault, never in plaintext code.</li>
      <li><strong>Compliance &amp; Retention:</strong> The client is responsible for ensuring TCPA compliance (caller consent to record). A standard 30-day data retention policy will be implemented for raw audio. Full regulatory audits (HIPAA, SOC2, GDPR) are outside the scope of this initial build.</li>
    </ul>
`;

const getCRGSOW = () => `
    <h1>Statement of Work (SOW)</h1>
    <p><strong>Project:</strong> CRG Backoffice Platform</p>
    <p><strong>Date:</strong> ${new Date().toLocaleDateString()}</p>
    
    <h2>1. Project Overview</h2>
    <p>The CRG Backoffice platform serves as the multi-tenant hub for managing flooring operations, municipal permit feeds, and workflow automation.</p>

    <h2>2. Scope of Work</h2>
    <ul>
      <li><strong>Multi-Tenancy Infrastructure:</strong> Core tenant isolation, per-tenant authentication, and Row Level Security (RLS).</li>
      <li><strong>Dynamic Plugin Architecture:</strong> Dynamic router inclusion and vertical feature registration.</li>
      <li><strong>Permit Feed Engine:</strong> Automated scanning and processing of municipal construction permits.</li>
    </ul>
`;

const getDefaultSOW = (name: string) => `
    <h1>Statement of Work (SOW)</h1>
    <p><strong>Project:</strong> ${name || "General Project"}</p>
    <p><strong>Date:</strong> ${new Date().toLocaleDateString()}</p>
    
    <h2>1. Project Overview</h2>
    <p>Statement of Work for <strong>${name || "Project"}</strong>. Detail objectives, scope, and deliverables below.</p>
    
    <h2>2. Scope of Work</h2>
    <ul>
      <li><strong>Milestone 1:</strong> Initial planning and requirements gathering.</li>
      <li><strong>Milestone 2:</strong> Core development and integration.</li>
      <li><strong>Milestone 3:</strong> Testing, verification, and deployment.</li>
    </ul>
`;

const getBoldNCSOW = () => `
<h2>1. Executive Summary & Project Identification</h2>
<p><strong>Project Name:</strong> BOLD NC Project Alpha (Governors Club)</p>
<p><strong>Client / Location:</strong> Governors Club Residence, Chapel Hill / Pittsboro, NC</p>
<p><strong>Contractor:</strong> CRG Flooring LLC</p>
<p><strong>Scope Overview:</strong> Supply, delivery, and turn-key installation of luxury vinyl plank (LVP) flooring for BOLD NC Project Alpha. Includes NC Form E-595E tax exemption handling, Will-Call logistics at MSI Surfaces Knightdale, subfloor moisture mitigation, and NCDOR sales tax compliance.</p>

<h2>2. Material Specifications & Supplier Order</h2>
<table border="1" cellpadding="8" style="border-collapse: collapse; width: 100%;">
  <thead>
    <tr style="background-color: rgba(184, 66, 46, 0.06);">
      <th style="text-align: left; padding: 10px; font-weight: 700;">Item Description</th>
      <th style="text-align: left; padding: 10px; font-weight: 700;">SKU / Product Code</th>
      <th style="text-align: left; padding: 10px; font-weight: 700;">Quantity</th>
      <th style="text-align: left; padding: 10px; font-weight: 700;">Coverage</th>
      <th style="text-align: left; padding: 10px; font-weight: 700;">Unit Price</th>
      <th style="text-align: left; padding: 10px; font-weight: 700;">Line Total</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="padding: 10px;"><strong>PRESCOTT - HONEYBELLA OAK 7.13X48.03</strong></td>
      <td style="padding: 10px;"><code>VTRHONBEL7X48-6.5MM-20MIL</code></td>
      <td style="padding: 10px;">128 Boxes</td>
      <td style="padding: 10px;">304.26 SF</td>
      <td style="padding: 10px;">$2.474 / SF</td>
      <td style="padding: 10px;"><strong>$752.64</strong></td>
    </tr>
  </tbody>
</table>

<h2>3. NC Sales & Use Tax Protocol</h2>
<p>Material is purchased from MSI with standard NC sales tax included at purchase ($752.64 net + tax). MSI remits state sales tax directly on behalf of CRG Flooring LLC, ensuring 100% legal compliance and zero state tax reporting burden.</p>

<h2>4. Logistics & Milestone Workflows</h2>
<ol>
  <li><strong>Order Placement:</strong> Submit PO for 128 boxes Prescott Honeybella Oak to Erandi Alvarez (MSI Knightdale) with tax included (~2.5 week NJ transit lead time).</li>
  <li><strong>Will-Call Logistics:</strong> Dispatch Will-Call pickup at 385 Spectrum Drive, Suite 100, Knightdale, NC 27545 upon arrival.</li>
  <li><strong>Subfloor Moisture Audit (Gate):</strong> Conduct relative humidity (RH) and surface moisture testing at Governors Club jobsite prior to installation.</li>
  <li><strong>Turn-Key Installation:</strong> Acclimate LVP planks 24h, install perimeter expansion gaps, and secure trim/transitions.</li>
  <li><strong>Close-out & Walkthrough:</strong> Perform final client walkthrough, collect sign-off, and issue final invoice.</li>
</ol>
`;

const isBlankHtml = (str: string | null) => {
  if (!str) return true;
  const cleaned = str.replace(/<[^>]*>/g, "").trim();
  return cleaned === "";
};

interface SOWGeneratorProps {
  projectId?: string;
  boardId?: string;
  boardName?: string;
  projectName?: string;
  cards?: any[];
}

export default function SOWGenerator({ projectId, boardId, boardName, projectName, cards = [] }: SOWGeneratorProps) {
  const [content, setContent] = useState<string>("");
  const [isAdhdMode, setIsAdhdMode] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [diagLog, setDiagLog] = useState<string>("Initializing...");
  const [sourceTag, setSourceTag] = useState<string>("LOADING");

  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const pid = boardId || projectId || (projectName ? projectName.replace(/[^a-zA-Z0-9]/g, "_") : "default");

  const getDefaultContent = () => {
    const target = `${projectName || ""} ${boardName || ""}`.toLowerCase();
    if (target.includes("claude corps") || target.includes("take-home")) {
      return getClaudeCorpsSOW();
    } else if (target.includes("nevermiss") || target.includes("never miss")) {
      return getNeverMissSOW();
    } else if (target.includes("bold")) {
      return getBoldNCSOW();
    } else if (target.includes("crg")) {
      return getCRGSOW();
    } else {
      return getDefaultSOW(boardName || projectName || "Project");
    }
  };

  const storageKey = useMemo(() => {
    const currentPid = boardId || projectId || (projectName ? projectName.replace(/[^a-zA-Z0-9]/g, "_") : "default");
    return `sow_content_v7_${currentPid}`;
  }, [boardId, projectId, projectName]);

  const fetchAndApplySOW = useCallback(async () => {
    const currentPid = boardId || projectId || (projectName ? projectName.replace(/[^a-zA-Z0-9]/g, "_") : "");
    const logInfo = `PID=${currentPid || "NONE"} | Board="${boardName || ""}" | Proj="${projectName || ""}"`;
    console.log(`[SOW_DIAGNOSTIC] Fetching SOW. ${logInfo}`);

    if (!currentPid) {
      setDiagLog(`Waiting for Board Context... (${logInfo})`);
      setSourceTag("WAITING");
      return;
    }

    setIsLoading(true);
    setDiagLog(`Querying PostgreSQL for ${currentPid}...`);

    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/sow?project_id=${encodeURIComponent(currentPid)}`, { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        console.log(`[SOW_DIAGNOSTIC] Backend response:`, data);
        if (data && data.exists && data.content && !isBlankHtml(data.content)) {
          setContent(data.content);
          localStorage.setItem(storageKey, data.content);
          setSourceTag("POSTGRES DB");
          setDiagLog(`Loaded from DB. Title: "${data.title || "Untitled"}" | Length: ${data.content.length} chars`);
          setIsLoading(false);
          return;
        }
      }
    } catch (err) {
      console.warn("[SOW_DIAGNOSTIC] Backend fetch error:", err);
    }

    const fresh = getDefaultContent();
    setContent(fresh);
    localStorage.setItem(storageKey, fresh);
    setSourceTag("FRESH DEFAULT");
    setDiagLog(`Generated Fresh Template for "${boardName || projectName || "Project"}"`);
    setIsLoading(false);
  }, [boardId, projectId, boardName, projectName, storageKey]);

  useEffect(() => {
    fetchAndApplySOW();
  }, [fetchAndApplySOW]);

  const handleForceReset = async () => {
    if (confirm("Reset SOW for this board to fresh template defaults?")) {
      localStorage.removeItem(storageKey);
      const fresh = getDefaultContent();
      setContent(fresh);
      setSourceTag("MANUAL RESET");
      setDiagLog("Reset to default template.");
      
      const currentPid = boardId || projectId || (projectName ? projectName.replace(/[^a-zA-Z0-9]/g, "_") : "default");
      try {
        await tenantFetch(`${API_BASE}/api/v1/sow`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_id: currentPid,
            project_name: projectName || boardName || "",
            board_id: boardId || "",
            content: fresh,
          }),
        });
      } catch (e) {
        console.error("Failed to reset DB SOW:", e);
      }
    }
  };

  const handleContentChange = (newContent: string) => {
    setContent(newContent);
    localStorage.setItem(storageKey, newContent);

    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    saveTimeoutRef.current = setTimeout(() => {
      const currentPid = boardId || projectId || (projectName ? projectName.replace(/[^a-zA-Z0-9]/g, "_") : "default");
      tenantFetch(`${API_BASE}/api/v1/sow`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: currentPid,
          project_name: projectName || boardName || "",
          board_id: boardId || "",
          content: newContent,
        }),
      }).catch(err => console.warn("Auto-save to backend SOW failed:", err));
    }, 1500);
  };
  
  const contentRef = useRef<HTMLDivElement>(null);
  const ReactQuill = useMemo(() => dynamic(() => import("react-quill-new"), { ssr: false }), []);

  const handleDownloadPdf = useReactToPrint({
    contentRef,
    documentTitle: `Statement_of_Work_${projectName?.replace(/\s+/g, "_") || "Project"}`,
  });
  
  const modules = useMemo(() => ({
    toolbar: [
      [{ header: [1, 2, 3, false] }],
      ["bold", "italic", "underline", "strike"],
      [{ color: [] }, { background: [] }],
      [{ list: "ordered" }, { list: "bullet" }],
      [{ indent: "-1" }, { indent: "+1" }],
      ["clean"],
    ],
  }), []);

  return (
    <div className="flex-1 flex flex-col h-full bg-neutral relative overflow-hidden font-sans text-primary">
      <div aria-hidden="true" className="absolute inset-0 pointer-events-none z-0 print:hidden">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:3.5rem_3.5rem] opacity-30 [mask-image:radial-gradient(ellipse_80%_80%_at_50%_20%,black_20%,transparent_100%)]" />
        <div className="absolute top-[-25%] right-[-15%] w-[50vw] h-[50vw] bg-tertiary/[0.03] rounded-full blur-[130px]" />
      </div>

      <header className="relative z-30 h-16 border-b border-border bg-card/90 backdrop-blur-md shadow-sm flex items-center justify-between px-4 sm:px-6 shrink-0 print:hidden gap-3 text-primary transition-colors">
        <div className="flex items-center gap-3.5 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-tertiary/10 border border-tertiary/30 flex items-center justify-center shrink-0 shadow-sm">
            <FileText className="w-4 h-4 text-tertiary" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-tertiary uppercase tracking-[0.2em] font-extrabold leading-none">
                Statement of Work
              </span>
              <span className="text-secondary/40 text-xs font-bold">•</span>
              <span className="text-xs font-mono font-bold text-secondary truncate max-w-[160px] sm:max-w-[280px]">
                {projectName || boardName || "Default Workspace"}
              </span>
            </div>
            <h2 className="font-serif text-base font-bold text-primary tracking-tight truncate mt-0.5">
              Document Editor
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* System Connection / Telemetry Badge with Dynamic Card Background */}
          <div
            className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-card border border-tertiary/40 rounded-full text-[10.5px] font-mono shadow-sm hover:border-tertiary transition-all cursor-help group relative"
            title={String(diagLog || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;")}
          >
            <span className="h-2 w-2 rounded-full bg-tertiary shadow-[0_0_8px_var(--tertiary,#e0b084)] animate-pulse"></span>
            <span className="font-bold text-tertiary tracking-wide uppercase text-[9.5px]">
              {sourceTag === "POSTGRES DB" ? "PostgreSQL Synced" : sourceTag}
            </span>

            <div className="absolute right-0 top-full mt-2 w-76 p-3 bg-card border border-border rounded-xl shadow-2xl backdrop-blur-xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 text-[10.5px] text-secondary font-mono leading-relaxed">
              <div className="flex items-center gap-2 text-primary font-bold mb-1 border-b border-border pb-1">
                <Database className="w-3.5 h-3.5 text-tertiary" /> Database Connection Status
              </div>
              <p className="text-secondary opacity-90 mt-1">{diagLog}</p>
            </div>
          </div>

          <button
            onClick={handleForceReset}
            className="h-9 px-3 bg-card hover:bg-neutral text-primary border border-border rounded-lg text-xs font-mono font-bold flex items-center gap-1.5 shadow-sm transition-all cursor-pointer shrink-0 active:scale-95"
            title="Reset template & clear local storage cache"
          >
            <RotateCcw className="w-3.5 h-3.5 text-secondary group-hover:rotate-180 transition-transform" />
            <span className="hidden sm:inline">Reset</span>
          </button>

          <button
            onClick={handleDownloadPdf}
            className="h-9 px-4 bg-tertiary text-white hover:opacity-90 font-sans text-xs font-bold rounded-lg shadow-md shadow-tertiary/20 flex items-center gap-2 transition-all cursor-pointer shrink-0 active:scale-95"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export PDF</span>
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto print:overflow-visible print:w-full print:bg-white bg-transparent py-8 pb-48 print:py-0 relative z-10">
        <div ref={contentRef} className="max-w-[816px] mx-auto bg-card artisan-shadow border border-border rounded-sm print:shadow-none print:border-none min-h-[1056px] print:min-h-0 print:w-full relative docs-editor mb-16 sm:mb-24 adhd-mode">
           <div className="p-4 sm:p-16 print:p-0 react-quill-wrapper">
            <ReactQuill
              theme="snow"
              value={content}
              onChange={handleContentChange}
              modules={modules}
            />
           </div>
        </div>
      </div>
      
      {/* Print and Quill Override Styles */}
      <style dangerouslySetInnerHTML={{__html: `
        @media print {
          html, body, #__next, main, div {
            height: auto !important;
            min-height: auto !important;
            overflow: visible !important;
            position: static !important;
          }
          body, .docs-editor {
            background-color: white !important;
            margin: 0;
            padding: 0;
          }
          header, nav, sidebar, .print\\\\:hidden, .ql-toolbar {
            display: none !important;
          }
          .custom-scrollbar {
             overflow: visible !important;
          }
          * {
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
          }
          .docs-editor * {
            color: black !important;
          }
          .docs-editor .ql-editor {
            font-size: 11pt !important;
          }
          .docs-editor.adhd-mode .ql-editor p:nth-child(odd),
          .docs-editor.adhd-mode .ql-editor li:nth-child(odd) {
             background-color: #f3f4f6 !important;
          }
          .docs-editor.adhd-mode .ql-editor p,
          .docs-editor.adhd-mode .ql-editor li {
             border-color: #e5e7eb !important;
             color: black !important;
          }
        }
        
        /* Blueprint-native Quill theme */
        /* Blueprint-native Quill theme */
        .docs-editor, .docs-editor.adhd-mode {
           background-color: var(--card) !important;
           height: max-content !important;
        }
        
        .docs-editor .react-quill-wrapper {
           height: max-content !important;
        }
        
        .docs-editor .react-quill-wrapper > div,
        .docs-editor .quill,
        .docs-editor .ql-container.ql-snow,
        .docs-editor .ql-editor {
          height: auto !important;
          min-height: max-content !important;
        }
        
        .docs-editor .ql-container.ql-snow {
          border: none !important;
          font-family: var(--font-sans) !important;
          height: auto !important;
          min-height: 800px;
        }
        .docs-editor .ql-editor {
          padding: 0;
          min-height: 800px;
          height: auto !important;
          overflow: visible !important;
          font-family: var(--font-sans) !important;
          font-size: 0.9375rem; /* 15px modern reading size */
          line-height: 1.7;
          color: var(--primary);
        }
        
        /* ADHD / Focus Reading Mode - Native System Font with Accessible Metrics */
        .docs-editor.adhd-mode .ql-editor p,
        .docs-editor.adhd-mode .ql-editor li,
        .docs-editor.adhd-mode .ql-editor h1,
        .docs-editor.adhd-mode .ql-editor h2,
        .docs-editor.adhd-mode .ql-editor h3 {
          font-family: var(--font-sans) !important; /* Premium system font */
          letter-spacing: 0.035em !important; /* Increased tracking for dyslexia */
          word-spacing: 0.15em !important; /* Explicit word separation */
          line-height: 2 !important; /* Cognitive breathing room */
        }
        .docs-editor.adhd-mode .ql-editor p,
        .docs-editor.adhd-mode .ql-editor li {
          padding: 8px 12px !important;
          border-bottom: 1px solid var(--border) !important;
          color: var(--secondary);
        }
        .docs-editor.adhd-mode .ql-editor p:nth-child(odd),
        .docs-editor.adhd-mode .ql-editor li:nth-child(odd) {
          background-color: rgba(128, 128, 128, 0.05) !important;
          border-radius: 6px;
        }
        
        .docs-editor .ql-editor strong,
        .docs-editor .ql-editor b {
          color: var(--primary);
        }
        .docs-editor .ql-editor h1,
        .docs-editor .ql-editor h1 span {
          font-family: var(--font-heading) !important;
          font-size: 2.25rem; /* 36px */
          font-weight: 600;
          letter-spacing: -0.02em;
          color: var(--tertiary) !important;
          margin-bottom: 1.25rem;
          margin-top: 1.5rem;
        }
        .docs-editor .ql-editor h2,
        .docs-editor .ql-editor h2 span {
          font-family: var(--font-heading) !important;
          font-size: 1.5rem; /* 24px */
          font-weight: 600;
          letter-spacing: -0.01em;
          color: var(--tertiary) !important;
          margin-bottom: 1rem;
          margin-top: 2rem;
          padding-bottom: 0.5rem;
          border-bottom: 1px solid var(--border);
        }
        .docs-editor .ql-editor h3 {
          font-family: var(--font-heading) !important;
          font-size: 1.25rem; /* 20px */
          font-weight: 600;
          color: var(--primary);
          margin-bottom: 0.75rem;
        }
        .docs-editor .ql-editor a { color: var(--tertiary); }
        .docs-editor .ql-editor ul, .docs-editor .ql-editor ol {
          padding-left: 1.5em;
          margin-bottom: 10pt;
        }

        /* Sticky Toolbar — matte paper, hairline base */
        .docs-editor .ql-toolbar.ql-snow {
           position: sticky !important;
           top: -32px; /* Offset the py-8 padding of the scroll container to eliminate the gap */
           z-index: 50;
           background: var(--card); /* Match document background */
           border: none !important;
           border-bottom: 1px solid var(--border) !important;
           padding: 12px 16px !important;
           margin: -40px -40px 24px -40px; /* Offset parent padding */
           border-radius: 4px 4px 0 0;
           display: flex !important;
           flex-wrap: wrap !important;
           gap: 6px !important;
           box-shadow: 0 4px 20px -10px rgba(0,0,0,0.1);
        }
        
        .docs-editor .ql-toolbar.ql-snow .ql-formats {
           display: flex;
           flex-wrap: wrap;
           margin-right: 8px !important;
        }

        @media (min-width: 640px) {
           .docs-editor .ql-toolbar.ql-snow {
              margin: -64px -64px 32px -64px;
           }
        }
        /* Boston Clay active/hover states for toolbar controls */
        .docs-editor .ql-snow.ql-toolbar button:hover .ql-stroke,
        .docs-editor .ql-snow.ql-toolbar button.ql-active .ql-stroke,
        .docs-editor .ql-snow.ql-toolbar .ql-picker-label:hover .ql-stroke,
        .docs-editor .ql-snow.ql-toolbar .ql-picker-item:hover .ql-stroke {
          stroke: var(--tertiary) !important;
        }
        .docs-editor .ql-snow.ql-toolbar button:hover .ql-fill,
        .docs-editor .ql-snow.ql-toolbar button.ql-active .ql-fill,
        .docs-editor .ql-snow.ql-toolbar .ql-picker-item:hover .ql-fill {
          fill: var(--tertiary) !important;
        }
        .docs-editor .ql-snow.ql-toolbar button:hover,
        .docs-editor .ql-snow.ql-toolbar button.ql-active,
        .docs-editor .ql-snow.ql-toolbar .ql-picker-label:hover,
        .docs-editor .ql-snow.ql-toolbar .ql-picker-label.ql-active,
        .docs-editor .ql-snow.ql-toolbar .ql-picker-item:hover,
        .docs-editor .ql-snow.ql-toolbar .ql-picker-item.ql-selected {
          color: var(--tertiary) !important;
        }

        /* Theme-Aware Code Tags, Monospace Elements, and Links */
        .docs-editor .ql-editor code,
        .docs-editor .ql-editor pre,
        .docs-editor .ql-editor var,
        .docs-editor .ql-editor kbd,
        .docs-editor .ql-editor samp {
          background-color: rgba(184, 66, 46, 0.06) !important;
          color: var(--tertiary) !important;
          border: 1px solid rgba(184, 66, 46, 0.2) !important;
          border-radius: 4px !important;
          padding: 2px 7px !important;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
          font-size: 0.85em !important;
          word-break: break-all !important;
        }

        .light .docs-editor .ql-editor code,
        .light .docs-editor .ql-editor pre,
        .light .docs-editor .ql-editor var,
        .light .docs-editor .ql-editor kbd,
        .light .docs-editor .ql-editor samp {
          background-color: rgba(26, 28, 30, 0.05) !important;
          color: #9E2B1E !important;
          border: 1px solid rgba(26, 28, 30, 0.15) !important;
        }

        .docs-editor .ql-editor a {
          color: var(--tertiary) !important;
          text-decoration: underline !important;
          text-underline-offset: 3px !important;
        }

        .docs-editor .ql-editor a code {
          color: var(--tertiary) !important;
          border-color: rgba(184, 66, 46, 0.3) !important;
        }

        /* High-Contrast Accessible Table Formatting */
        .docs-editor .ql-editor table {
          width: 100% !important;
          border-collapse: collapse !important;
          margin: 1.5rem 0 !important;
          font-size: 0.875rem !important;
          border: 1px solid var(--border) !important;
          border-radius: 6px !important;
          overflow: hidden !important;
        }
        .docs-editor .ql-editor th,
        .docs-editor .ql-editor td {
          padding: 10px 14px !important;
          border: 1px solid var(--border) !important;
          text-align: left !important;
          vertical-align: top !important;
          color: var(--primary) !important;
        }
        .docs-editor .ql-editor th {
          background-color: var(--sand) !important;
          color: var(--primary) !important;
          font-weight: 700 !important;
          font-family: var(--font-data) !important;
          text-transform: uppercase !important;
          font-size: 0.75rem !important;
          letter-spacing: 0.05em !important;
          border-bottom: 2px solid var(--border) !important;
        }
        .docs-editor .ql-editor tr:nth-child(even) td {
          background-color: rgba(128, 128, 128, 0.03) !important;
        }
        .docs-editor .ql-editor tr:hover td {
          background-color: var(--sand) !important;
        }
      `}} />
    </div>
  );
}
