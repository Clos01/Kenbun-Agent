const sqlite3 = require("/usr/local/lib/node_modules/n8n/node_modules/sqlite3");
const db = new sqlite3.Database("/home/node/.n8n/database.sqlite");

const nodes = [
  {
    "parameters": {
      "path": "gmail-reply-push",
      "httpMethod": "POST",
      "options": {}
    },
    "id": "push-webhook-trigger",
    "name": "Webhook: Gmail Reply Push",
    "type": "n8n-nodes-base.webhook",
    "typeVersion": 1,
    "position": [250, 300]
  },
  {
    "parameters": {
      "jsCode": "const body = $json.body || $json;\nconst text = body.reply_text || body.snippet || body.textPlain || 'Approve';\nconst company = body.company_name || 'TWP GARNER RETAIL LLC';\nconst email = body.target_email || 'bids@twpgarnerretail.com';\nconst client = body.client_name || 'TWP Garner Retail';\nreturn [{ json: { reply_text: text, company_name: company, client_name: client, target_email: email } }];"
    },
    "id": "parse-reply-data",
    "name": "Parse Reply Data",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [450, 300]
  },
  {
    "parameters": {
      "method": "POST",
      "url": "http://100.100.199.127:8001/api/v1/intelligence/process-reply",
      "sendBody": true,
      "specifyBody": "json",
      "jsonBody": "={{ JSON.stringify($json) }}",
      "options": {}
    },
    "id": "ai-reply-router",
    "name": "FastMCP CRG Backoffice Router",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.1,
    "position": [650, 300]
  },
  {
    "parameters": {
      "sendTo": "={{ $json.target_email || 'rivascreativeagency@gmail.com' }}",
      "subject": "={{ $json.subject || '[REVISED BRIEF] CRG Flooring Outreach' }}",
      "emailType": "html",
      "message": "={{ $json.formatted_approval_email || $json.final_body }}",
      "options": {}
    },
    "id": "gmail-dispatch",
    "name": "Send Mobile Reply Back to Carlos",
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

const connections = {
  "Webhook: Gmail Reply Push": {
    "main": [
      [
        {
          "node": "Parse Reply Data",
          "type": "main",
          "index": 0
        }
      ]
    ]
  },
  "Parse Reply Data": {
    "main": [
      [
        {
          "node": "FastMCP CRG Backoffice Router",
          "type": "main",
          "index": 0
        }
      ]
    ]
  },
  "FastMCP CRG Backoffice Router": {
    "main": [
      [
        {
          "node": "Send Mobile Reply Back to Carlos",
          "type": "main",
          "index": 0
        }
      ]
    ]
  }
};

const versionId = new Date().toISOString();
db.run(
  `UPDATE workflow_entity SET nodes = ?, connections = ?, active = 1, versionId = ? WHERE id = 'MOBILE_REPLY_LOOP'`,
  [JSON.stringify(nodes), JSON.stringify(connections), versionId],
  (err) => {
    if (err) {
      console.error("Error updating n8n DB:", err);
      process.exit(1);
    } else {
      console.log("SUCCESS: MOBILE_REPLY_LOOP updated to Webhook Push Endpoint /webhook/gmail-reply-push!");
      process.exit(0);
    }
  }
);
