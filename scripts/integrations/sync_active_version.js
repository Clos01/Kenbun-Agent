const sqlite3 = require("/usr/local/lib/node_modules/n8n/node_modules/sqlite3");
const db = new sqlite3.Database("/home/node/.n8n/database.sqlite");

db.get("SELECT nodes, connections FROM workflow_entity WHERE id='EOTQpewzNOwVCUIC'", (err, row) => {
  if (err || !row) {
    console.error("Workflow entity not found:", err);
    process.exit(1);
  }

  const nodes = row.nodes;
  const connections = row.connections;
  const targetVersionId = "cf9070be-3965-4554-8626-0c786123f62f";
  const now = new Date().toISOString();

  // Update existing active version in workflow_history
  db.run(
    `UPDATE workflow_history SET nodes = ?, connections = ?, updatedAt = ? WHERE versionId = ? AND workflowId = 'EOTQpewzNOwVCUIC'`,
    [nodes, connections, now, targetVersionId],
    (err2) => {
      if (err2) {
        console.error("Error updating workflow_history:", err2);
        process.exit(1);
      }

      // Update workflow_entity versionId & activeVersionId
      db.run(
        `UPDATE workflow_entity SET versionId = ?, activeVersionId = ?, active = 1 WHERE id = 'EOTQpewzNOwVCUIC'`,
        [targetVersionId, targetVersionId],
        (err3) => {
          if (err3) {
            console.error("Error updating workflow_entity:", err3);
            process.exit(1);
          } else {
            console.log("SUCCESS: Synchronized activeVersionId:", targetVersionId);
            process.exit(0);
          }
        }
      );
    }
  );
});
