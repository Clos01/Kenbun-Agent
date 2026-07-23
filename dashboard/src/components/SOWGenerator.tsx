import React, { useState, useMemo } from "react";
import { Download, FileText } from "lucide-react";
import dynamic from "next/dynamic";
import "react-quill-new/dist/quill.snow.css";

// Dynamic import with SSR disabled for Quill editor
const ReactQuill = dynamic(() => import("react-quill-new"), { ssr: false });

export default function SOWGenerator() {
  const [content, setContent] = useState<string>(`
    <h1>Statement of Work (SOW)</h1>
    <p><strong>Client:</strong> NeverMiss.ai</p>
    <p><strong>Date:</strong> ${new Date().toLocaleDateString()}</p>
    
    <h2>1. Project Overview (Updated Live: ${new Date().toLocaleTimeString()})</h2>
    <p>NeverMiss.ai requires a <strong>Self-Improving Fleet Management System</strong> for its ElevenLabs voice agents. The goal is to monitor the performance of all deployed agents from a single pane of glass, automatically evaluate every call, ingest client feedback when an agent makes a mistake, and dynamically push improved instructions back to the ElevenLabs API to prevent future errors.</p>
    <p><em>Meeting Update (Jul 22):</em> Initial iterations will utilize a <strong>Human-in-the-Loop</strong> process. Evaluations will be presented to the developer for manual approval via email/dashboard before updates are pushed automatically to the ElevenLabs agents. This ensures strict quality control before full automation.</p>
    
    <h2>2. Scope of Work</h2>
    <ul>
      <li><strong>Automated Voice Evaluations (Self-Reflection):</strong> Setting up a pipeline that automatically grades 100% of calls against a custom quality rubric to identify where an agent faltered.</li>
      <li><strong>Dynamic Agent Updating:</strong> When an agent fails an evaluation or receives negative client feedback, an LLM will automatically analyze the failure, draft improved prompt instructions, and push the update directly to the ElevenLabs API to correct the agent's behavior.</li>
      <li><strong>Fleet Monitoring Dashboard:</strong> Designing a single-pane-of-glass analytics dashboard to see how <em>all</em> deployed agents are performing across the entire company.</li>
    </ul>
    
    <h2>3. Deliverables</h2>
    <ol>
      <li>Fleet Monitoring Dashboard (Built with Next.js and Tailwind)</li>
      <li>Self-Improving Evaluation &amp; Update Pipeline (Integrating directly with ElevenLabs API)</li>
      <li>Client Feedback Ingestion Portal</li>
    </ol>
    
    <h2>4. Architecture &amp; Technology Stack</h2>
    <ul>
      <li><strong>Workflow Automation (n8n):</strong> The core data processing pipeline will route post-call webhooks from ElevenLabs directly into n8n. This allows for rapid parsing, AI evaluation (via Gemini), and seamless database integration without the overhead of maintaining a heavy custom backend.</li>
      <li><strong>Database (Managed Azure PostgreSQL):</strong> A fully managed Azure PostgreSQL database (P4 Burstable Tier, 32GB) will securely store structured call transcripts and evaluation data. This avoids the maintenance and security overhead of a local VM.</li>
      <li><strong>Real-Time Streaming (SSE):</strong> Live call data will be pushed directly to the Next.js dashboard, creating a real-time, word-for-word typing effect.</li>
    </ul>
    
    <h2>5. Timeline &amp; Phases</h2>
    <ul>
      <li><strong>Phase 1 (Weeks 1-8):</strong> Core development and monitoring. Building the n8n workflow, establishing the Azure database, designing the live dashboard, and manually monitoring agent performance (Human-in-the-Loop).</li>
      <li><strong>Future Phases (TBD):</strong> Upon successful validation of Phase 1, additional security layers (e.g., prompt injection monitoring), autonomous agent updates without human intervention, and advanced analytics will be scoped.</li>
    </ul>
    
    <h2>6. Payment Terms</h2>
    <ul>
      <li><strong>Rate:</strong> $24/hour</li>
      <li><strong>Estimated Hours:</strong> Minimum 10 hours per week</li>
      <li><strong>Invoicing Frequency:</strong> Weekly</li>
    </ul>
    
    <h2>7. Client Responsibilities &amp; Access</h2>
    <p>To ensure security and compliance, the client agrees to provision access using role-based invites rather than shared passwords. The following access is required before development begins:</p>
    <ul>
      <li><strong>Developer/Admin Invites:</strong> Role-based access to the ElevenLabs workspace.</li>
      <li><strong>API Secrets:</strong> The following keys must be transmitted via a secure, one-time self-destructing link (e.g., One-Time Secret) rather than email or chat:
        <ul>
          <li>ElevenLabs API Key (for transcript and webhook access)</li>
          <li>Anthropic or OpenAI API Key (for the automated 7-point voice grading pipeline)</li>
          <li>Booking / CRM Auth Tokens (for testing webhook integrations)</li>
        </ul>
      </li>
      <li><strong>Sandbox Environment &amp; Testing:</strong> To ensure live business metrics, customer notifications, and real client bookings are completely unaffected during our development cycles, the client must provision:
        <ul>
          <li><strong>Isolated CRM/Calendar:</strong> A dedicated "Test User" account and an isolated calendar (e.g., a blank Google Calendar or Cal.com link) strictly for testing the AI's booking logic.</li>
          <li><strong>Test Agent & Voice Number:</strong> A dedicated ElevenLabs test agent and a separate phone number used exclusively for development and webhook testing.</li>
          <li><strong>Disabled Live Notifications:</strong> The sandbox environment must have all outbound customer SMS and email reminders disabled so we do not accidentally send test messages to real customers.</li>
        </ul>
      </li>
      <li><strong>In-Office Collaboration:</strong> The developer will coordinate in-person whiteboard sessions at the office a couple of days a week for architectural alignment and team building, while maintaining the flexibility of remote, off-hours development.</li>
    </ul>
    
    <h2>8. Data Security &amp; Compliance</h2>
    <p>Given the handling of voice recordings and transcripts, the following security measures will be implemented:</p>
    <ul>
      <li><strong>Data Encryption:</strong> All call recordings, transcripts, and PII will be encrypted at rest (AES-256) and in transit (TLS 1.3).</li>
      <li><strong>Secret Management:</strong> Production API keys and database credentials will be stored exclusively in AWS Secrets Manager or Azure Key Vault, never in plaintext code.</li>
      <li><strong>Compliance &amp; Retention:</strong> The client is responsible for ensuring TCPA compliance (caller consent to record). A standard 30-day data retention policy will be implemented for raw audio. Full regulatory audits (HIPAA, SOC2, GDPR) are outside the scope of this initial build.</li>
    </ul>
  `);

  const handleDownloadPdf = () => {
    window.print();
  };

  const modules = useMemo(() => ({
    toolbar: [
      [{ header: [1, 2, 3, false] }],
      ["bold", "italic", "underline", "strike"],
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
        <button
          onClick={handleDownloadPdf}
          className="px-3 py-1.5 bg-primary text-neutral hover:bg-primary/90 rounded text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 transition-colors cursor-pointer shrink-0"
        >
          <Download className="w-3.5 h-3.5" />
          Export PDF
        </button>
      </header>

      {/* Full Page Editor — white "paper" sheet floats over the matte grid */}
      <div className="flex-1 overflow-y-auto print:overflow-visible print:w-full print:bg-white bg-transparent py-8 print:py-0 relative z-10">
        <div className="max-w-[816px] mx-auto bg-card artisan-shadow border border-border rounded-sm print:shadow-none print:border-none min-h-[1056px] print:min-h-0 print:w-full relative docs-editor">
           <div className="p-10 sm:p-16 print:p-0">
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
          body {
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
            color: black !important;
          }
        }
        
        /* Heritage-native Quill theme (Boston Clay accent, Cormorant headings) */
        .docs-editor .ql-container.ql-snow {
          border: none !important;
          font-family: var(--font-sans);
        }
        .docs-editor .ql-editor {
          padding: 0;
          min-height: 800px;
          font-size: 11pt;
          line-height: 1.7;
          color: var(--primary);
        }
        .docs-editor .ql-editor h1 {
          font-family: var(--font-heading);
          font-size: 26pt;
          font-weight: 600;
          letter-spacing: -0.02em;
          color: var(--primary);
          margin-bottom: 16pt;
          margin-top: 10pt;
        }
        .docs-editor .ql-editor h2 {
          font-family: var(--font-heading);
          font-size: 17pt;
          font-weight: 600;
          letter-spacing: -0.01em;
          color: var(--primary);
          margin-bottom: 10pt;
          margin-top: 16pt;
          padding-bottom: 4pt;
          border-bottom: 1px solid var(--border);
        }
        .docs-editor .ql-editor h3 {
          font-family: var(--font-heading);
          font-size: 14pt;
          font-weight: 600;
          color: var(--primary);
          margin-bottom: 8pt;
        }
        .docs-editor .ql-editor p {
          color: var(--primary);
          margin-bottom: 10pt;
        }
        .docs-editor .ql-editor strong { color: var(--primary); }
        .docs-editor .ql-editor a { color: var(--tertiary); }
        .docs-editor .ql-editor ul, .docs-editor .ql-editor ol {
          padding-left: 1.5em;
          margin-bottom: 10pt;
        }
        .docs-editor .ql-editor li {
          margin-bottom: 4pt;
        }

        /* Sticky Toolbar — matte paper, hairline base */
        .docs-editor .ql-toolbar.ql-snow {
           position: sticky !important;
           top: 0;
           z-index: 50;
           background: var(--neutral);
           border: none !important;
           border-bottom: 1px solid var(--border) !important;
           padding: 10px 16px !important;
           margin: -40px -40px 24px -40px; /* Offset parent padding */
           border-radius: 4px 4px 0 0;
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
