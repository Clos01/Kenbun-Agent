const sqlite3 = require("/usr/local/lib/node_modules/n8n/node_modules/sqlite3");
const db = new sqlite3.Database("/home/node/.n8n/database.sqlite");

db.get("SELECT nodes, connections FROM workflow_entity WHERE id='EOTQpewzNOwVCUIC'", (err, row) => {
  if (err || !row) {
    console.error("Workflow entity not found:", err);
    process.exit(1);
  }

  const nodes = row.nodes;
  const connections = row.connections;
  const newVersionId = "cf9070be-3965-4554-8626-0c786123f799";
  const now = new Date().toISOString();

  // Insert matching record into workflow_history
  db.run(
    `INSERT OR REPLACE INTO workflow_history (versionId, workflowId, nodes, connections, authors, createdAt, updatedAt) VALUES (?, 'EOTQpewzNOwVCUIC', ?, ?, '[]', ?, ?)`,
    [newVersionId, nodes, connections, now, now],
    (err2) => {
      if (err2) {
        console.error("Error inserting workflow_history:", err2);
        process.exit(1);
      }

      // Update workflow_entity activeVersionId
      db.run(
        `UPDATE workflow_entity SET versionId = ?, activeVersionId = ?, active = 1 WHERE id = 'EOTQpewzNOwVCUIC'`,
        [newVersionId, newVersionId],
        (err3) => {
          if (err3) {
            console.error("Error updating workflow_entity:", err3);
            process.exit(1);
          } else {
            console.log("SUCCESS: Synchronized workflow_history and workflow_entity with versionId:", newVersionId);
            process.exit(0);
          }
        }
      );
    }
  );
});
