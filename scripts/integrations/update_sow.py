import re

file_path = "/home/carlos/dev/workspace/kenbun/dashboard/src/components/SOWGenerator.tsx"
with open(file_path, "r") as f:
    content = f.read()

new_sow = """
    <h1>Statement of Work & Project Recap: Claude Corps Fellowship</h1>
    <p><strong>Client:</strong> Riverbend Food Alliance</p>
    <p><strong>Date:</strong> ${new Date().toLocaleDateString()}</p>
    
    <h2>1. Overall Objective</h2>
    <p>Act as the new AI Fellow at Riverbend Food Alliance to automate inbox triage, audit quarterly board data, design a volunteer confirmation architecture, and calculate the ROI of AI automation.</p>

    <h2>2. Task Breakdown & Defenses</h2>
    
    <h3>The Triage Prompt (Email 1)</h3>
    <ul>
      <li><strong>Action Taken:</strong> Wrote an AI prompt for Claude 3 Haiku to categorize incoming emails at <code>donate@</code>.</li>
      <li><strong>The Logic (Security Pivot):</strong> 
        <ul>
          <li>Forced the AI to return <strong>strict JSON</strong> (using enums) rather than free-text responses to prevent hallucinations.</li>
          <li>Hardcoded a rule: <strong><code>draft: null</code> for Major Donors</strong>. This ensures the AI cannot make unauthorized commitments to VIPs, keeping a human (Marcus) firmly in the loop for high-liability relationships.</li>
        </ul>
      </li>
    </ul>

    <h3>The Data Audit (Email 2)</h3>
    <ul>
      <li><strong>Action Taken:</strong> Fact-checked Diane's draft Q1 Board Memo against raw Excel exports.</li>
      <li><strong>The Logic (Data Verification):</strong>
        <ul>
          <li>Didn't blindly trust the AI's surface-level summary. Forced a deep merge of the Excel sheets and used cross-model checks.</li>
          <li><strong>The "T-99" Catch:</strong> Used <code>cmd+f</code> cross-referencing to find a dummy test truck (<code>T-99</code>) hiding ~47,000 lbs of fake weight that would have severely skewed the final report.</li>
          <li>Cleaned up spelling duplicates (e.g., 'Mt Zion' vs 'Mt. Zion') that were causing false 'crisis' flags.</li>
        </ul>
      </li>
    </ul>

    <h3>The Volunteer Architecture (Email 3)</h3>
    <ul>
      <li><strong>Action Taken:</strong> Sketched a volunteer confirmation flowchart in HTML.</li>
      <li><strong>The Logic (Sovereign & Secure Design):</strong>
        <ul>
          <li><strong>No CDNs:</strong> Explicitly avoided external CDNs (like Mermaid.js) so the HTML would load reliably offline.</li>
          <li><strong>Sovereign Stack / MCP:</strong> Instead of relying on a standard Airtable SaaS, integrated <strong>MCP (Model Context Protocol)</strong> with your Sovereign Stack (local PostgreSQL, n8n, Ollama). This allows the AI to read/write securely to your local database without human copy-pasting.</li>
          <li><strong>Exception Handling:</strong> Implemented a 'Monday Verification Check' to keep a human in the loop for edge cases.</li>
        </ul>
      </li>
    </ul>

    <h3>The Budget Math (Email 4)</h3>
    <ul>
      <li><strong>Action Taken:</strong> Calculated the monthly API costs for triaging the emails.</li>
      <li><strong>The Logic (ROI Calculation):</strong>
        <ul>
          <li>Pulled the peak volume of 1,800 emails/month from the team handbook.</li>
          <li>Estimated ~1,500 tokens per email on Claude Haiku, demonstrating a worst-case scenario cost of under $5/month, which yields massive ROI in saved human hours.</li>
          <li><strong>The Sovereign Pivot:</strong> By leveraging local models on your Sovereign Stack (Ollama), those recurring inference costs can actually be pushed to near zero!</li>
        </ul>
      </li>
    </ul>

    <h2>3. Core Interview Themes to Remember</h2>
    <ul>
      <li><strong>Speed vs. Accuracy:</strong> "I use AI to accelerate the initial heavy lifting, but I rely on human verification and cross-model checks for critical constraints."</li>
      <li><strong>Risk-Based Auditing:</strong> "I lock down the AI's boundaries using strict JSON and human-in-the-loop rules for high-liability tasks."</li>
      <li><strong>Data Sovereignty:</strong> "I prioritize offline reliability and secure local data pipelines (MCP + Local Postgres) over cloud-dependent SaaS."</li>
    </ul>
"""

pattern = r"(useState<string>\(\`)(.*?)(\`\);)"
new_file_content = re.sub(pattern, lambda m: f"{m.group(1)}\n{new_sow}\n{m.group(3)}", content, flags=re.DOTALL)

with open(file_path, "w") as f:
    f.write(new_file_content)
print("Updated successfully.")
