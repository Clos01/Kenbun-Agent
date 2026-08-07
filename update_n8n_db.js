const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3');
const db = new sqlite3.Database('/home/node/.n8n/database.sqlite');

const webhookUuid = "9d9ef504-20a8-4c8d-b0a7-19602e6c5222";

const newNodes = [
  {
    "parameters": {
      "httpMethod": "POST",
      "path": "flooring-lead-capture",
      "options": {}
    },
    "id": "webhook-lead-v3",
    "name": "Webhook: Lead Input",
    "type": "n8n-nodes-base.webhook",
    "typeVersion": 1.1,
    "position": [250, 300],
    "webhookId": webhookUuid
  },
  {
    "parameters": {
      "method": "POST",
      "url": "http://100.100.199.127:8001/api/v1/intelligence/generate-outreach",
      "sendBody": true,
      "specifyBody": "json",
      "jsonBody": "={{ JSON.stringify({ client_name: $json.body.name || 'Valued Partner', company_name: $json.body.company_name || 'Commercial Client', address: $json.body.address || 'the local area', type: $json.body.work_class || 'Commercial Flooring', email: $json.body.email || $json.body.contact_email || '', value: $json.body.value || '$200,000', match_score: $json.body.score ? ($json.body.score + '%') : '100%', permit_class: $json.body.permit_class || 'Construction / Issued', work_details: $json.body.work_details || $json.body.description || 'Interior alterations per engineered drawings.', source: $json.body.source || 'PlankMap Scraper API' }) }}",
      "options": {}
    },
    "id": "ai-outreach-draft-v3",
    "name": "AI Outreach Draft Engine",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.1,
    "position": [550, 300]
  },
  {
    "parameters": {
      "sendTo": "rivascreativeagency@gmail.com",
      "subject": "={{ $json.subject }}",
      "emailType": "html",
      "message": "={{ $json.formatted_approval_email }}",
      "options": {}
    },
    "id": "gmail-approval-v3",
    "name": "Send Mobile Approval Email to Carlos",
    "type": "n8n-nodes-base.gmail",
    "typeVersion": 2.1,
    "position": [850, 300],
    "credentials": {
      "gmailOAuth2": {
        "id": "yXZ9ShTXUIeuwqNW",
        "name": "Gmail account"
      }
    }
  }
];

const newConnections = {
  "Webhook: Lead Input": {
    "main": [
      [
        {
          "node": "AI Outreach Draft Engine",
          "type": "main",
          "index": 0
        }
      ]
    ]
  },
  "AI Outreach Draft Engine": {
    "main": [
      [
        {
          "node": "Send Mobile Approval Email to Carlos",
          "type": "main",
          "index": 0
        }
      ]
    ]
  }
};

const nowISO = new Date().toISOString();

db.serialize(() => {
  db.run("DELETE FROM webhook_entity");
  db.run(
    "INSERT INTO webhook_entity (workflowId, webhookPath, method, node, webhookId, pathLength) VALUES ('EOTQpewzNOwVCUIC', 'flooring-lead-capture', 'POST', 'Webhook: Lead Input', ?, 21)",
    [webhookUuid]
  );
  db.run(
    "UPDATE workflow_entity SET name=?, nodes=?, connections=?, updatedAt=?, active=1 WHERE id='EOTQpewzNOwVCUIC'",
    ["Flooring Lead Autonomous Approval Pipeline V7 (Real Recipient Email Support)", JSON.stringify(newNodes), JSON.stringify(newConnections), nowISO]
  );
  db.run(
    "UPDATE workflow_history SET nodes=?, connections=? WHERE workflowId='EOTQpewzNOwVCUIC'",
    [JSON.stringify(newNodes), JSON.stringify(newConnections)]
  );
  db.run("PRAGMA wal_checkpoint(FULL)", (err) => {
    if (err) console.error(err);
    else console.log("SUCCESSFULLY UPDATED V7 DYNAMIC RECIPIENT EMAIL PIPELINE!");
  });
});
