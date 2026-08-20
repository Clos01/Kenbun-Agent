const sqlite3 = require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3');
const db = new sqlite3.Database('/home/node/.n8n/database.sqlite');

const workflowId = "MOBILE_REPLY_REVISION_LOOP";

const replyNodes = [
  {
    "parameters": {
      "pollTimes": {
        "item": [
          {
            "mode": "everyMinute"
          }
        ]
      },
      "filters": {
        "q": "subject:(APPROVAL REQ)"
      },
      "options": {}
    },
    "id": "gmail-trigger-reply",
    "name": "Gmail Trigger: Carlos Reply",
    "type": "n8n-nodes-base.gmailTrigger",
    "typeVersion": 1.1,
    "position": [250, 300],
    "credentials": {
      "gmailOAuth2": {
        "id": "yXZ9ShTXUIeuwqNW",
        "name": "Gmail account"
      }
    }
  },
  {
    "parameters": {
      "method": "POST",
      "url": "http://100.100.199.127:8001/api/v1/intelligence/process-reply",
      "sendBody": true,
      "specifyBody": "json",
      "jsonBody": "={{ JSON.stringify({ reply_text: $json.textPlain || $json.snippet || 'Approve', lead_id: $json.subject, company_name: $json.subject ? $json.subject.replace(/.*\\]\\s*/, '') : 'Steve Jolley Builders', client_name: 'Steve Jolley', target_email: 'steve@stevejolleybuilders.com' }) }}",
      "options": {}
    },
    "id": "ai-reply-router",
    "name": "AI Mobile Reply Processor",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.1,
    "position": [550, 300]
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
                "typeValidation": "strict"
              },
              "conditions": [
                {
                  "leftValue": "={{ $json.status }}",
                  "rightValue": "APPROVED",
                  "operator": {
                    "type": "string",
                    "operation": "equals"
                  }
                }
              ],
              "combinator": "and"
            },
            "renameOutput": true,
            "outputKey": "Approved"
          },
          {
            "conditions": {
              "options": {
                "caseSensitive": true,
                "leftValue": "",
                "typeValidation": "strict"
              },
              "conditions": [
                {
                  "leftValue": "={{ $json.status }}",
                  "rightValue": "REVISED",
                  "operator": {
                    "type": "string",
                    "operation": "equals"
                  }
                }
              ],
              "combinator": "and"
            },
            "renameOutput": true,
            "outputKey": "Revised"
          }
        ]
      },
      "options": {}
    },
    "id": "switch-action",
    "name": "Check Action Status",
    "type": "n8n-nodes-base.switch",
    "typeVersion": 3,
    "position": [850, 300]
  },
  {
    "parameters": {
      "sendTo": "={{ $json.target_email }}",
      "subject": "={{ $json.final_subject }}",
      "message": "={{ $json.final_body }}",
      "options": {}
    },
    "id": "gmail-dispatch-contractor",
    "name": "Dispatch Outreach to Contractor",
    "type": "n8n-nodes-base.gmail",
    "typeVersion": 2.1,
    "position": [1150, 200],
    "credentials": {
      "gmailOAuth2": {
        "id": "yXZ9ShTXUIeuwqNW",
        "name": "Gmail account"
      }
    }
  },
  {
    "parameters": {
      "sendTo": "rivascreativeagency@gmail.com",
      "subject": "={{ $json.subject }}",
      "emailType": "html",
      "message": "={{ $json.formatted_approval_email }}",
      "options": {}
    },
    "id": "gmail-resend-revised-brief",
    "name": "Resend Revised Brief to Carlos",
    "type": "n8n-nodes-base.gmail",
    "typeVersion": 2.1,
    "position": [1150, 400],
    "credentials": {
      "gmailOAuth2": {
        "id": "yXZ9ShTXUIeuwqNW",
        "name": "Gmail account"
      }
    }
  }
];

const replyConnections = {
  "Gmail Trigger: Carlos Reply": {
    "main": [
      [
        {
          "node": "AI Mobile Reply Processor",
          "type": "main",
          "index": 0
        }
      ]
    ]
  },
  "AI Mobile Reply Processor": {
    "main": [
      [
        {
          "node": "Check Action Status",
          "type": "main",
          "index": 0
        }
      ]
    ]
  },
  "Check Action Status": {
    "main": [
      [
        {
          "node": "Dispatch Outreach to Contractor",
          "type": "main",
          "index": 0
        }
      ],
      [
        {
          "node": "Resend Revised Brief to Carlos",
          "type": "main",
          "index": 0
        }
      ]
    ]
  }
};

const nowISO = new Date().toISOString();

db.serialize(() => {
  db.run("DELETE FROM workflow_entity WHERE id='MOBILE_REPLY_LOOP'");
  db.run(
    "INSERT INTO workflow_entity (id, name, nodes, connections, createdAt, updatedAt, active, versionId) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
    [
      "MOBILE_REPLY_LOOP",
      "Mobile Reply & Bi-Directional Revision Loop Engine",
      JSON.stringify(replyNodes),
      JSON.stringify(replyConnections),
      nowISO,
      nowISO,
      nowISO
    ]
  );
  db.run(
    "DELETE FROM workflow_history WHERE workflowId='MOBILE_REPLY_LOOP'"
  );
  db.run(
    "INSERT INTO workflow_history (versionId, workflowId, nodes, connections, createdAt, authors) VALUES (?, 'MOBILE_REPLY_LOOP', ?, ?, ?, 'Carlos')",
    [nowISO, JSON.stringify(replyNodes), JSON.stringify(replyConnections), nowISO]
  );
  db.run("PRAGMA wal_checkpoint(FULL)", (err) => {
    if (err) console.error(err);
    else console.log("SUCCESSFULLY INSTALLED MOBILE REPLY & REVISION LOOP WORKFLOW IN DATABASE!");
  });
});
