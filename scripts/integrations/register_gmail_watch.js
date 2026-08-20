const sqlite3 = require("/usr/local/lib/node_modules/n8n/node_modules/sqlite3");
const db = new sqlite3.Database("/home/node/.n8n/database.sqlite");

// We create a temporary workflow to execute the Gmail API watch registration
const node = {
  "parameters": {
    "method": "POST",
    "url": "https://gmail.googleapis.com/gmail/v1/users/me/watch",
    "authentication": "predefinedCredentialType",
    "nodeCredentialType": "gmailOAuth2",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": JSON.stringify({
      "topicName": "projects/gen-lang-client-0940374584/topics/gmail-push-topic",
      "labelIds": ["INBOX"]
    })
  },
  "id": "gmail-watch-node",
  "name": "Register Gmail Watch",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.1,
  "position": [200, 200],
  "credentials": {
    "gmailOAuth2": {
      "id": "yXZ9ShTXUIeuwqNW",
      "name": "Gmail account"
    }
  }
};

console.log("Registering Gmail Watch via n8n node structure...");
