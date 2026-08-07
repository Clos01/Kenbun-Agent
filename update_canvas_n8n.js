const sqlite3 = require("/usr/local/lib/node_modules/n8n/node_modules/sqlite3");
const db = new sqlite3.Database("/home/node/.n8n/database.sqlite");

const nodes = [
  // ── Branch 0: Schedule Watch Renewal ───────────────────────────────────────
  {
    "parameters": {
      "rule": {
        "interval": [
          {
            "field": "days",
            "seconds": 86400
          }
        ]
      }
    },
    "id": "schedule-watch-trigger",
    "name": "Schedule Watch Renewal",
    "type": "n8n-nodes-base.scheduleTrigger",
    "typeVersion": 1.2,
    "position": [200, 100]
  },
  {
    "parameters": {
      "method": "POST",
      "url": "https://gmail.googleapis.com/gmail/v1/users/me/watch",
      "authentication": "predefinedCredentialType",
      "nodeCredentialType": "gmailOAuth2",
      "sendBody": true,
      "specifyBody": "json",
      "jsonBody": JSON.stringify({
        "topicName": "projects/kenbun-n8n/topics/kenbun-n8n",
        "labelIds": ["INBOX"]
      }),
      "options": {}
    },
    "id": "register-gmail-watch",
    "name": "Register Gmail API Push Watch",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.1,
    "position": [450, 100],
    "credentials": {
      "gmailOAuth2": {
        "id": "yXZ9ShTXUIeuwqNW",
        "name": "Gmail account"
      }
    }
  },

  // ── Branch 1: Lead Capture ────────────────────────────────────────────────
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
    "position": [200, 300],
    "webhookId": "9d9ef504-20a8-4c8d-b0a7-19602e6c5222"
  },
  {
    "parameters": {
      "jsCode": `
const body = $json.body || $json;

if (body.subscription || (body.message && body.message.data && !body.work_details)) {
  return [{ json: { ignore: true } }];
}

return [{
  json: {
    ignore: false,
    client_name: body.client_name || body.name || 'Commercial Tower Estimating Team',
    company_name: body.company_name || 'COMMERCIAL TOWER RALEIGH LLC',
    email: body.email || body.target_email || 'bids@commercialtowerraleigh.com',
    target_email: body.email || body.target_email || 'bids@commercialtowerraleigh.com',
    phone: body.phone || '(919) 555-0199',
    address: body.address || '555 Fayetteville St, Raleigh, NC 27601',
    type: body.work_class || body.type || 'Commercial Flooring',
    work_class: body.work_class || 'New Commercial Facility',
    value: body.value || '$1,250,000.00',
    score: body.score || 100,
    permit_class: body.permit_class || 'New Commercial Building / Issued',
    work_details: body.work_details || '12-Story Commercial Tower development. Commercial broadloom carpet, LVP, modular carpet tile, and hardwood installations.',
    source: body.source || 'PlankMap Commercial Open Data API'
  }
}];
`
    },
    "id": "parse-lead-data",
    "name": "Parse Lead Data",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [450, 300]
  },
  {
    "parameters": {
      "method": "POST",
      "url": "http://100.100.199.127:8001/api/v1/intelligence/generate-outreach",
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
    "id": "ai-lead-draft-engine",
    "name": "AI CRG Lead Draft Engine",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.1,
    "position": [700, 300]
  },

  // ── Branch 2: Mobile Reply Push ───────────────────────────────────────────
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
    "position": [200, 550],
    "webhookId": "gmail-reply-push-id"
  },
  {
    "parameters": {
      "method": "GET",
      "url": "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=1",
      "authentication": "predefinedCredentialType",
      "nodeCredentialType": "gmailOAuth2"
    },
    "id": "get-latest-gmail-msg",
    "name": "Fetch Latest Gmail Message",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.1,
    "position": [380, 550],
    "credentials": {
      "gmailOAuth2": {
        "id": "yXZ9ShTXUIeuwqNW",
        "name": "Gmail account"
      }
    }
  },
  {
    "parameters": {
      "method": "GET",
      "url": "=https://gmail.googleapis.com/gmail/v1/users/me/messages/{{ $json.messages[0].id }}",
      "authentication": "predefinedCredentialType",
      "nodeCredentialType": "gmailOAuth2"
    },
    "id": "get-gmail-msg-detail",
    "name": "Get Gmail Message Detail",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.1,
    "position": [550, 550],
    "credentials": {
      "gmailOAuth2": {
        "id": "yXZ9ShTXUIeuwqNW",
        "name": "Gmail account"
      }
    }
  },
  {
    "parameters": {
      "jsCode": `
const msg = $json;
const snippet = msg.snippet || '';
const threadId = msg.threadId || '';
const headers = (msg.payload && msg.payload.headers) || [];

const getHeader = (name) => {
  const h = headers.find(item => item.name.toLowerCase() === name.toLowerCase());
  return h ? h.value : '';
};

const subjectHeader = getHeader('Subject');

// IMMUTABLE LOOP GUARD: Ignore any message that contains AI system card markers or template text
if (
  !snippet ||
  snippet.includes('PLANKMAP') ||
  snippet.includes('Mobile Approval Actions') ||
  snippet.includes('[Field Edit Instruction]') ||
  snippet.includes('Outreach Email Approved') ||
  snippet.includes('Generated automatically by CRG') ||
  snippet.includes('CRG Swarm') ||
  snippet.includes('Captured Lead Details') ||
  snippet.includes('Proposed Outreach Email')
) {
  return [{ json: { ignore: true } }];
}

let company_name = 'COMMERCIAL TOWER RALEIGH LLC';
if (subjectHeader.includes(':')) {
  company_name = subjectHeader.split(':').slice(1).join(':').trim();
} else if (subjectHeader.includes(']')) {
  company_name = subjectHeader.split(']').slice(1).join(']').trim();
}

return [{
  json: {
    ignore: false,
    reply_text: snippet,
    company_name: company_name,
    threadId: threadId,
    target_email: 'bids@commercialtowerraleigh.com'
  }
}];
`
    },
    "id": "parse-mobile-reply",
    "name": "Parse Mobile Reply Data",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [720, 550]
  },
  {
    "parameters": {
      "rules": {
        "values": [
          {
            "conditions": {
              "options": {
                "caseSensitive": true,
                "leftValue": "",
                "typeValidation": "strict",
                "version": 2
              },
              "conditions": [
                {
                  "leftValue": "={{ $json.ignore }}",
                  "rightValue": false,
                  "operator": {
                    "type": "boolean",
                    "operation": "equals"
                  }
                }
              ],
              "combinator": "and"
            },
            "renameOutput": true,
            "outputKey": "Valid Reply"
          }
        ]
      },
      "options": {}
    },
    "id": "filter-mobile-reply",
    "name": "Filter Mobile Reply",
    "type": "n8n-nodes-base.switch",
    "typeVersion": 3,
    "position": [880, 550]
  },
  {
    "parameters": {
      "method": "POST",
      "url": "http://100.100.199.127:8001/api/v1/intelligence/process-reply",
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
    "id": "ai-mobile-reply-engine",
    "name": "AI CRG Mobile Reply Engine",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.1,
    "position": [1040, 550]
  },

  // ── Unified Email Brief Dispatch Node ────────────────────────────────────
  {
    "parameters": {
      "resource": "message",
      "operation": "send",
      "sendTo": "rivascreativeagency@gmail.com",
      "subject": "={{ $json.subject || $json.outreach_subject || '[APPROVAL REQ] New CRG Commercial Lead' }}",
      "emailType": "html",
      "message": "={{ $json.formatted_approval_email || $json.message || $json.outreach_body || 'Outreach process updated successfully.' }}",
      "options": {
        "threadId": "={{ $json.threadId || '' }}"
      }
    },
    "id": "gmail-send-carlos",
    "name": "Send Mobile Executive Brief to Carlos",
    "type": "n8n-nodes-base.gmail",
    "typeVersion": 2.1,
    "position": [1200, 425],
    "credentials": {
      "gmailOAuth2": {
        "id": "yXZ9ShTXUIeuwqNW",
        "name": "Gmail account"
      }
    }
  }
];

const connections = {
  "Schedule Watch Renewal": {
    "main": [[{ "node": "Register Gmail API Push Watch", "type": "main", "index": 0 }]]
  },
  "Webhook: Lead Input": {
    "main": [[{ "node": "Parse Lead Data", "type": "main", "index": 0 }]]
  },
  "Parse Lead Data": {
    "main": [[{ "node": "AI CRG Lead Draft Engine", "type": "main", "index": 0 }]]
  },
  "AI CRG Lead Draft Engine": {
    "main": [[{ "node": "Send Mobile Executive Brief to Carlos", "type": "main", "index": 0 }]]
  },
  "Webhook: Gmail Reply Push": {
    "main": [[{ "node": "Fetch Latest Gmail Message", "type": "main", "index": 0 }]]
  },
  "Fetch Latest Gmail Message": {
    "main": [[{ "node": "Get Gmail Message Detail", "type": "main", "index": 0 }]]
  },
  "Get Gmail Message Detail": {
    "main": [[{ "node": "Parse Mobile Reply Data", "type": "main", "index": 0 }]]
  },
  "Parse Mobile Reply Data": {
    "main": [[{ "node": "Filter Mobile Reply", "type": "main", "index": 0 }]]
  },
  "Filter Mobile Reply": {
    "main": [
      [{ "node": "AI CRG Mobile Reply Engine", "type": "main", "index": 0 }]
    ]
  },
  "AI CRG Mobile Reply Engine": {
    "main": [[{ "node": "Send Mobile Executive Brief to Carlos", "type": "main", "index": 0 }]]
  }
};

const versionId = "cf9070be-3965-4554-8626-0c786123f62f";
db.run(
  `UPDATE workflow_entity SET nodes = ?, connections = ?, active = 0, versionId = ?, activeVersionId = ? WHERE id = 'EOTQpewzNOwVCUIC'`,
  [JSON.stringify(nodes), JSON.stringify(connections), versionId, versionId],
  (err) => {
    if (err) {
      console.error("Error updating canvas in DB:", err);
      process.exit(1);
    } else {
      console.log("SUCCESS: Workflow EOTQpewzNOwVCUIC updated with Immutable Loop Guard!");
      process.exit(0);
    }
  }
);
