const http = require("http");
const url = require("url");
const crypto = require("crypto");

const PORT = 8001;
// Support standard UUID format (v1-v5) case-insensitive
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Mock datasets partitioned by tenant_id
function getInitialMockLeads() {
  return {
    // Tenant A: Real Estate
    "4ba4e6b2-a42e-4b68-b789-f5383569c7ad": [
      {
        id: "90a9b836-e82a-4a6c-b3a1-2d7c5b61e27a",
        name: "Luxury Penthouse Acquisition",
        tenant_id: "4ba4e6b2-a42e-4b68-b789-f5383569c7ad",
        metadata: {
          budget: "$1,500,000",
          request_date: "2026-07-06",
          commercial: false,
          location: "Downtown Core",
          collections: ["residential", "luxury"]
        }
      },
      {
        id: "1c80efc2-7ba4-4fe1-ba76-d1883be71e29",
        name: "Suburban Family Estate",
        tenant_id: "4ba4e6b2-a42e-4b68-b789-f5383569c7ad",
        metadata: {
          budget: "$650,000",
          request_date: "2026-07-07",
          commercial: false,
          location: "Greenwood Valley",
          collections: ["residential", "family"]
        }
      }
    ],
    // Tenant B: Landscaping
    "2ef1a364-e81c-4b65-bd29-c88349282fed": [
      {
        id: "8c7f9382-749e-4c72-9cf0-e1837c73b28b",
        name: "Residential Lawn Renewal",
        tenant_id: "2ef1a364-e81c-4b65-bd29-c88349282fed",
        metadata: {
          budget: "$4,200",
          request_date: "2026-07-06",
          commercial: false,
          location: "Boston Suburbs",
          collections: ["residential", "sodding"]
        }
      },
      {
        id: "3df1a364-e81c-4b65-bd29-c88349282fed",
        name: "Commercial Office Park Turf",
        tenant_id: "2ef1a364-e81c-4b65-bd29-c88349282fed",
        metadata: {
          budget: 15000,          // Intended coercion testing: number budget
          request_date: "2026-07-08",
          commercial: "true",      // Intended coercion testing: string "true"
          recurring: "weekly"
        }
      }
    ],
    // Tenant C: Malicious
    "8c7f9382-749e-4c72-9cf0-e1837c73b28b": [
      {
        id: "a1a9b836-e82a-4a6c-b3a1-2d7c5b61e27a",
        name: "Exploit Lead Attempt",
        tenant_id: "8c7f9382-749e-4c72-9cf0-e1837c73b28b",
        metadata: {
          budget: "$10,000",
          request_date: "2026-07-07",
          commercial: true,
          // Adversarial parameters to test validation stripping and sanitization
          isAdmin: true,
          delete_all_records: "DROP TABLE leads;",
          "__proto__": { "polluted": true },
          "inject_script": "<script>alert('XSS')</script>",
          "onload_exploit": "<img src=x onerror=alert(1)>"
        }
      }
    ],
    // Tenant D: Empty
    "a6f02844-0b1a-45c1-90c7-2c1a85cd17e3": []
  };
}

let mockLeads = getInitialMockLeads();

const server = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url, true);
  const pathname = parsedUrl.pathname;

  console.log(`[MOCK API] Request: method=${req.method}, url=${req.url}, pathname=${pathname}`);

  // CORS Headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "x-tenant-id, Content-Type, Authorization");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  // Reset endpoint
  if (req.method === "POST" && (pathname === "/api/backend/reset" || pathname === "/api/reset")) {
    mockLeads = getInitialMockLeads();
    console.log("[MOCK API] Database state reset to initial mock datasets.");
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "success", message: "Database reset complete" }));
    return;
  }

  // Health endpoint
  if (pathname === "/api/health" || pathname === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "healthy" }));
    return;
  }

  // Leads endpoint
  if (pathname === "/api/backend/leads") {
    const tenantId = req.headers["x-tenant-id"] || parsedUrl.query.tenant_id;
    console.log(`[MOCK API] Resolved tenantId: ${tenantId}`);

    if (!tenantId) {
      res.writeHead(401, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Unauthorized: Missing tenant ID" }));
      return;
    }

    if (!UUID_REGEX.test(tenantId)) {
      console.log(`[MOCK API] UUID validation FAILED for tenantId: ${tenantId}`);
      res.writeHead(400, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Bad Request: Invalid tenant ID format" }));
      return;
    }

    if (req.method === "GET") {
      const responseData = mockLeads[tenantId] || [];
      console.log(`[MOCK API] Returning ${responseData.length} leads for tenantId: ${tenantId}`);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(responseData));
      return;
    }

    if (req.method === "POST") {
      let body = "";
      req.on("data", (chunk) => { body += chunk; });
      req.on("end", () => {
        try {
          const newLead = JSON.parse(body);
          newLead.id = crypto.randomUUID();
          newLead.tenant_id = tenantId;
          
          if (!mockLeads[tenantId]) {
            mockLeads[tenantId] = [];
          }
          mockLeads[tenantId].push(newLead);
          
          res.writeHead(201, { "Content-Type": "application/json" });
          res.end(JSON.stringify(newLead));
        } catch (err) {
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "Bad Request: Malformed payload JSON" }));
        }
      });
      return;
    }
  }

  // Fallback 404
  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "Not Found" }));
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`Mock Server listening on http://127.0.0.1:${PORT}`);
});
