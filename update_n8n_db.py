import sqlite3
import json
import sys

db_path = "/home/node/.n8n/database.sqlite"
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT id, name, nodes FROM workflow_entity WHERE id='EOTQpewzNOwVCUIC'")
row = c.fetchone()
if not row:
    print("Workflow not found!")
    sys.exit(1)

nodes = json.loads(row[2])

sub_expr = "={{ '[APPROVAL REQ #' + Math.floor(1000 + Math.random()*9000) + '] ' + ($('Webhook: Lead Input1').item.json.body.company_name || $('Webhook: Lead Input1').item.json.body.name) }}"

msg_expr = """={{ "==================================================\\n📊 B2B LEAD INTELLIGENCE BRIEF\\n==================================================\\n• 🏢 Company: " + ($('Webhook: Lead Input1').item.json.body.company_name || 'Commercial Contractor') + "\\n• 👤 Contact Name: " + $('Webhook: Lead Input1').item.json.body.name + "\\n• 📍 Location/Address: " + $('Webhook: Lead Input1').item.json.body.address + "\\n• 🔍 Lead Findings / Request: " + ($('Webhook: Lead Input1').item.json.body.work_class || 'Commercial Flooring') + "\\n• 🛡️ Anti-Spam Verification: Passed (Checked Google Sheets — Not emailed in past 30 days)\\n\\n==================================================\\n✉️ PROPOSED OUTREACH EMAIL (CJ PERSONA)\\n==================================================\\nTo: " + ($('Webhook: Lead Input1').item.json.body.email || 'client@example.com') + "\\nSubject: Vendor Roster Inquiry - CRG Flooring (" + ($('Webhook: Lead Input1').item.json.body.company_name || 'Commercial Client') + ")\\n\\nHi " + $('Webhook: Lead Input1').item.json.body.name + ",\\n\\nMy name is CJ with CRG Flooring. I hope your week is off to a great start.\\n\\nI'm reaching out to introduce our team and inquire about the process to join " + ($('Webhook: Lead Input1').item.json.body.company_name || 'your team') + "'s Approved Subcontractor / Vendor List for upcoming commercial flooring projects in " + $('Webhook: Lead Input1').item.json.body.address + ".\\n\\nWe specialize in commercial carpet, LVP, tile, and hardwood installation. We take pride in delivering dependable, top-tier craftsmanship on schedule and within scope.\\n\\nWould you be open to pointing me toward the right contact or vendor application form? You can also check out our capabilities at https://crgflooring.com.\\n\\nThanks for your time, and I look forward to connecting!\\n\\nBest regards,\\n\\nCJ | CRG Flooring\\nDirect: (984) 212-1721\\nhttps://crgflooring.com\\n\\n==================================================\\n📱 MOBILE APPROVAL ACTIONS\\n==================================================\\n• Reply \\"Approve\\" (or \\"Send\\") -> Antigravity & n8n send this email to the contractor.\\n• Reply with edits (e.g. \\"Ask if they prefer online form or PDF\\") -> AI updates draft and sends you a revised preview.\\n• Reply \\"Reject\\" -> Cancels outreach." }}"""

for n in nodes:
    if n.get("name") == "Gmail: VIP Notification1":
        n["parameters"]["subject"] = sub_expr
        n["parameters"]["message"] = msg_expr
        print("Updated Gmail: VIP Notification1 parameters!")

c.execute("UPDATE workflow_entity SET nodes=? WHERE id='EOTQpewzNOwVCUIC'", (json.dumps(nodes),))
conn.commit()
print("Successfully committed updated workflow nodes to SQLite!")
