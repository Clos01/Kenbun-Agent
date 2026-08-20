import sqlite3
import json

db_path = "/home/its_los/.n8n/database.sqlite"
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT id, name, nodes FROM workflow_entity WHERE id='EOTQpewzNOwVCUIC'")
row = c.fetchone()
if row:
    nodes = json.loads(row[2])
    for n in nodes:
        if n.get("name") == "Gmail: VIP Notification1":
            n["parameters"]["subject"] = "={{ '[APPROVAL REQ #LEAD-' + Math.floor(1000 + Math.random()*9000) + '] Lead: ' + $json.Name + ' - ' + $json.Type }}"
            n["parameters"]["message"] = (
                "={{ 'Hey Carlos,\\n\\n' +"
                "'AI has drafted the following client outreach email for your review:\\n\\n' +"
                "'--------------------------------------------------\\n' +"
                "'To: ' + ($json.Email || 'client@example.com') + '\\n' +"
                "'Subject: Estimate Follow-up: Flooring Project\\n\\n' +"
                "'Hi ' + $json.Name + ',\\n\\n' +"
                "'Thank you for reaching out regarding your flooring project at ' + $json.Address + '.\\n\\n' +"
                "'We would love to schedule a quick estimate call to discuss your options. We take pride in delivering top-quality flooring craftsmanship across the area.\\n\\n' +"
                "'Please let me know if a quick 10-minute estimate call works best for your schedule!\\n\\n' +"
                "'Best regards,\\nCarlos Rivas\\nCRG Flooring\\n' +"
                "'--------------------------------------------------\\n\\n' +"
                "'📱 HOW TO APPROVE FROM YOUR PHONE:\\n' +"
                "'• Reply \"Approve\" or \"Send\" -> Sends this email to the client.\\n' +"
                "'• Reply with instructions (e.g. \"Change price to $4,500 and start Monday\") -> AI updates draft and sends you a revised preview.\\n' +"
                "'• Reply \"Reject\" -> Cancels outreach.' }}"
            )
            print("Found and updated Gmail node!")
    
    c.execute("UPDATE workflow_entity SET nodes=? WHERE id='EOTQpewzNOwVCUIC'", (json.dumps(nodes),))
    conn.commit()
    print("Database committed successfully!")
conn.close()
