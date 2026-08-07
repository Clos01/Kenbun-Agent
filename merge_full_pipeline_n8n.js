const sqlite3 = require("/usr/local/lib/node_modules/n8n/node_modules/sqlite3");
const db = new sqlite3.Database("/home/node/.n8n/database.sqlite");

const nodes = [
  // ── Top Section 1: Schedule & Google Calendar ──────────────────────────────
  {
    "parameters": {
      "rule": {
        "interval": [{ "field": "minutes", "minutesInterval": 60 }]
      }
    },
    "id": "schedule-trigger",
    "name": "Schedule Trigger",
    "type": "n8n-nodes-base.scheduleTrigger",
    "typeVersion": 1.2,
    "position": [200, 100]
  },
  {
    "parameters": {
      "operation": "getAll",
      "calendar": "primary",
      "options": {}
    },
    "id": "google-calendar",
    "name": "Google Calendar",
    "type": "n8n-nodes-base.googleCalendar",
    "typeVersion": 1,
    "position": [450, 100],
    "credentials": {
      "googleCalendarOAuth2Api": {
        "id": "googleCalendarOAuth2Credential",
        "name": "Google Calendar account"
      }
    }
  },

  // ── Top Section 2: Error Trigger Watchdog ──────────────────────────────────
  {
    "parameters": {},
    "id": "error-trigger",
    "name": "Error Trigger",
    "type": "n8n-nodes-base.errorTrigger",
    "typeVersion": 1,
    "position": [200, 250]
  },
  {
    "parameters": {
      "method": "POST",
      "url": "https://hook.us1.make.com/alert-watchdog",
      "sendBody": true,
      "specifyBody": "json",
      "jsonBody": "={{ JSON.stringify({ error: $json, timestamp: new Date().toISOString() }) }}",
      "options": {}
    },
    "id": "http-alert",
    "name": "HTTP Request (Alert)",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.1,
    "position": [450, 250]
  },

  // ── Main Section 3: Webhook Leads & Gmail Reply Push ───────────────────────
  {
    "parameters": {
      "path": "flooring-lead-capture",
      "httpMethod": "POST",
      "options": {}
    },
    "id": "webhook-lead-input",
    "name": "Webhook: Lead Input",
    "type": "n8n-nodes-base.webhook",
    "typeVersion": 1,
    "position": [200, 500]
  },
  {
    "parameters": {
      "path": "gmail-reply-push",
      "httpMethod": "POST",
      "options": {}
    },
    "id": "webhook-gmail-push",
    "name": "Webhook: Gmail Reply Push",
    "type": "n8n-nodes-base.webhook",
    "typeVersion": 1,
    "position": [200, 680]
  },

  // ── Quality Gate Code Node ────────────────────────────────────────────────
  {
    "parameters": {
      "jsCode": `
const body = $json.body || $json;
const isReply = !!(body.is_mobile_reply || (body.reply_text && body.reply_text !== 'Approve'));

if (isReply) {
  return [{
    json: {
      is_mobile_reply: true,
      reply_text: body.reply_text || 'Approve',
      company_name: body.company_name || 'HAYES BARTON HOMES INC',
      client_name: body.client_name || 'Hayes Barton Commercial Division',
      target_email: body.email || body.target_email || 'bids@hayesbartonhomes.com',
      address: body.address || '1433 Chester Rd, Raleigh, NC 27608'
    }
  }];
} else {
  return [{
    json: {
      is_mobile_reply: false,
      client_name: body.client_name || body.name || 'Hayes Barton Commercial Division',
      company_name: body.company_name || 'HAYES BARTON HOMES INC',
      email: body.email || body.target_email || 'bids@hayesbartonhomes.com',
      target_email: body.target_email || body.email || 'bids@hayesbartonhomes.com',
      phone: body.phone || '(919) 555-0144',
      address: body.address || '1433 Chester Rd, Raleigh, NC 27608',
      type: body.work_class || body.type || 'Commercial Flooring',
      work_class: body.work_class || 'New Commercial Facility',
      value: body.value || '$833,043.60',
      score: body.score || 100,
      permit_class: body.permit_class || 'New Building / Issued',
      work_details: body.work_details || 'Commercial flooring installation',
      source: body.source || 'PlankMap Open Data API'
    }
  }];
}
`
    },
    "id": "quality-gate",
    "name": "Quality Gate (Code)",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [450, 580]
  },

  // ── Save to Google Sheets ─────────────────────────────────────────────────
  {
    "parameters": {
      "operation": "append",
      "sheetId": "1CRG_Flooring_Leads_Sheet_ID",
      "options": {}
    },
    "id": "save-google-sheets",
    "name": "Save to Google Sheets",
    "type": "n8n-nodes-base.googleSheets",
    "typeVersion": 4.4,
    "position": [680, 580],
    "alwaysOutputData": true,
    "onError": "continueRegularOutput"
  },

  // ── Sync to Planka CRM & FastMCP Engine ──────────────────────────────────
  {
    "parameters": {
      "method": "POST",
      "url": "={{ $json.is_mobile_reply ? 'http://100.100.199.127:8001/api/v1/intelligence/process-reply' : 'http://100.100.199.127:8001/api/v1/intelligence/generate-outreach' }}",
      "sendHeaders": true,
      "headerParameters": {
        "parameters": [
          {
            "name": "Content-Type",
            "value": "application/json"
          }
        ]
      },
      "sendBody": true,
      "specifyBody": "json",
      "jsonBody": "={{ JSON.stringify($json) }}",
      "options": {}
    },
    "id": "sync-planka-crm",
    "name": "Sync to Planka CRM & FastMCP Engine",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.1,
    "position": [900, 580],
    "onError": "continueRegularOutput"
  },

  // ── Smart Router (Score) ──────────────────────────────────────────────────
  {
    "parameters": {
      "rules": {
        "values": [
          {
            "conditions": {
              "options": { "caseSensitive": true, "leftValue": "", "typeValidation": "strict" },
              "conditions": [
                {
                  "leftValue": "={{ $json.score || 100 }}",
                  "rightValue": 50,
                  "operator": { "type": "number", "operation": "gte" }
                }
              ],
              "combinator": "and"
            },
            "renameOutput": true,
            "outputKey": "Qualified Lead (>=50%)"
          }
        ]
      },
      "options": {}
    },
    "id": "smart-router",
    "name": "Smart Router (Score)",
    "type": "n8n-nodes-base.switch",
    "typeVersion": 3.1,
    "position": [1120, 580]
  },

  // ── Send Mobile Executive Brief to Carlos ────────────────────────────────
  {
    "parameters": {
      "resource": "message",
      "operation": "send",
      "sendTo": "rivascreativeagency@gmail.com",
      "subject": "={{ $json.subject || $json.outreach_subject || '[APPROVAL REQ] New CRG Commercial Lead' }}",
      "emailType": "html",
      "message": "={{ $json.formatted_approval_email }}",
      "options": {}
    },
    "id": "gmail-send-carlos",
    "name": "Gmail: VIP Notification",
    "type": "n8n-nodes-base.gmail",
    "typeVersion": 2.1,
    "position": [1350, 500],
    "credentials": {
      "gmailOAuth2": {
        "id": "yXZ9ShTXUIeuwqNW",
        "name": "Gmail account"
      }
    }
  },
  {
    "parameters": {},
    "id": "no-action",
    "name": "No Action",
    "type": "n8n-nodes-base.noOp",
    "typeVersion": 1,
    "position": [1350, 680]
  }
];

const connections = {
  "Schedule Trigger": {
    "main": [[{ "node": "Google Calendar", "type": "main", "index": 0 }]]
  },
  "Error Trigger": {
    "main": [[{ "node": "HTTP Request (Alert)", "type": "main", "index": 0 }]]
  },
  "Webhook: Lead Input": {
    "main": [[{ "node": "Quality Gate (Code)", "type": "main", "index": 0 }]]
  },
  "Webhook: Gmail Reply Push": {
    "main": [[{ "node": "Quality Gate (Code)", "type": "main", "index": 0 }]]
  },
  "Quality Gate (Code)": {
    "main": [[
      { "node": "Save to Google Sheets", "type": "main", "index": 0 },
      { "node": "Sync to Planka CRM & FastMCP Engine", "type": "main", "index": 0 }
    ]]
  },
  "Sync to Planka CRM & FastMCP Engine": {
    "main": [[{ "node": "Smart Router (Score)", "type": "main", "index": 0 }]]
  },
  "Smart Router (Score)": {
    "main": [
      [{ "node": "Gmail: VIP Notification", "type": "main", "index": 0 }],
      [{ "node": "No Action", "type": "main", "index": 0 }]
    ]
  }
};

const versionId = new Date().toISOString();
db.run(
  `UPDATE workflow_entity SET nodes = ?, connections = ?, active = 1, versionId = ?, activeVersionId = ? WHERE id = 'EOTQpewzNOwVCUIC'`,
  [JSON.stringify(nodes), JSON.stringify(connections), versionId, versionId],
  (err) => {
    if (err) {
      console.error("Error merging full pipeline n8n DB:", err);
      process.exit(1);
    } else {
      console.log("SUCCESS: Full Pipeline (Calendar + Error Watchdog + Sheets + Planka + Push Webhook + Smart Router) updated and published in EOTQpewzNOwVCUIC!");
      process.exit(0);
    }
  }
);
