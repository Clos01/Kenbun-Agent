import React, { useState, useMemo, useEffect, useRef } from "react";
import { Download, FileText, Loader2 } from "lucide-react";
import dynamic from "next/dynamic";
import { useReactToPrint } from "react-to-print";
import "react-quill-new/dist/quill.snow.css";

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

const isBlankHtml = (str: string | null) => {
  if (!str) return true;
  const cleaned = str.replace(/<[^>]*>/g, "").trim();
  return cleaned === "";
};


interface SOWGeneratorProps {
  boardId?: string;
  boardName?: string;
  projectName?: string;
}

export default function SOWGenerator({ boardId, boardName, projectName }: SOWGeneratorProps) {
  const [content, setContent] = useState<string>("");
  const [isAdhdMode, setIsAdhdMode] = useState<boolean>(false);

  const getDefaultContent = () => {
    const combined = `${projectName || ""} ${boardName || ""}`.toLowerCase();
    if (combined.includes("claude corps") || combined.includes("take-home assessment")) {
      return getClaudeCorpsSOW();
    } else if (combined.includes("nevermiss") || combined.includes("backend") || combined.includes("azure") || combined.includes("webhook") || combined.includes("infra")) {
      return getNeverMissSOW();
    } else if (combined.includes("crg")) {
      return getCRGSOW();
    } else {
      return getDefaultSOW(projectName || boardName || "Project");
    }
  };

  useEffect(() => {
    const key = boardId ? `sow_content_v3_${boardId}` : "sow_content_v3_global";
    const saved = localStorage.getItem(key);
    
    // Check if the saved content is the generic boilerplate. If so, discard it so the heuristic can run again.
    const isGeneric = saved && saved.includes("Statement of Work for <strong>Project</strong>") && !saved.includes("NeverMiss");

    if (saved && !isBlankHtml(saved) && !saved.includes("Sovereign Stack Overview") && !isGeneric) {
      setContent(saved);
    } else {
      if (boardId) {
        localStorage.removeItem(`sow_content_${boardId}`);
        localStorage.removeItem(`sow_content_v2_${boardId}`);
        localStorage.removeItem(`sow_content_v3_${boardId}`);
      }
      const fresh = getDefaultContent();
      setContent(fresh);
      localStorage.setItem(key, fresh);
    }
  }, [boardId, boardName, projectName]);
  const contentRef = useRef<HTMLDivElement>(null);

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
      {/* Heritage backdrop — faded drafting grid + matte clay wash, so the editor reads as part of the app */}
      <div aria-hidden="true" className="absolute inset-0 pointer-events-none z-0 print:hidden">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:3.5rem_3.5rem] opacity-30 [mask-image:radial-gradient(ellipse_80%_80%_at_50%_20%,black_20%,transparent_100%)]" />
        <div className="absolute top-[-25%] right-[-15%] w-[50vw] h-[50vw] bg-tertiary/[0.03] rounded-full blur-[130px]" />
      </div>

      {/* Header toolbar — mirrors the board header (label-caps eyebrow + serif-italic title, matte glass) */}
      <header className="relative z-30 h-12 border-b border-primary/10 bg-neutral/85 backdrop-blur-sm flex items-center justify-between px-4 sm:px-6 shrink-0 print:hidden gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <FileText className="w-4 h-4 text-tertiary shrink-0" />
          <div className="min-w-0">
            <div className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold leading-none mb-0.5">Statement of Work</div>
            <h2 className="font-serif italic text-sm font-bold text-primary leading-tight truncate">Document Editor</h2>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDownloadPdf}
          className="px-3 py-1.5 bg-primary text-neutral hover:bg-primary/90 rounded text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 transition-colors cursor-pointer shrink-0"
        >
          <Download className="w-3.5 h-3.5" />
          Export PDF
        </button>
        </div>
      </header>

      {/* Full Page Editor — white "paper" sheet floats over the matte grid */}
      <div className="flex-1 overflow-y-auto print:overflow-visible print:w-full print:bg-white bg-transparent py-8 pb-48 print:py-0 relative z-10">
        <div ref={contentRef} className="max-w-[816px] mx-auto bg-card artisan-shadow border border-border rounded-sm print:shadow-none print:border-none min-h-[1056px] print:min-h-0 print:w-full relative docs-editor mb-16 sm:mb-24 adhd-mode" style={{ backgroundColor: "var(--card, #121212)" }}>
           <div className="p-10 sm:p-16 print:p-0 react-quill-wrapper">
            <ReactQuill
              theme="snow"
              value={content}
              onChange={setContent}
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
        
        /* Heritage-native Quill theme */
        /* Heritage-native Quill theme */
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
        .docs-editor .ql-editor h1 {
          font-family: var(--font-heading) !important;
          font-size: 2.25rem; /* 36px */
          font-weight: 600;
          letter-spacing: -0.02em;
          color: var(--tertiary);
          margin-bottom: 1.25rem;
          margin-top: 1.5rem;
        }
        .docs-editor .ql-editor h2 {
          font-family: var(--font-heading) !important;
          font-size: 1.5rem; /* 24px */
          font-weight: 600;
          letter-spacing: -0.01em;
          color: var(--tertiary);
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
      `}} />
    </div>
  );
}
