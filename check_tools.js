const fs = require('fs');

const pasted = `consult supervisor
audit guardrail
research official docs
ask architect
ask ui expert
get design tokens
review code with gemini
research with gemini
run code safely
scan repo
remember fix
recall fix
save checkpoint
restore checkpoint
list checkpoints
orchestrate
gemini review
remember result
reflect
research
guardrail audit
supervisor review
read file
supervisor audit
token governor
telemetry pulse
fleet monitor
topology mapper
audit supervisor
vector sync worker
bayesian governor
sovereignty engine
memory classifier
neural classifier
intelligence engine
index codebase
delete from hivemind
get brain health
audit package safety
autofix linter
save to hivemind
search hivemind concepts
search codebase
think about tools
patch hivemind concept
ingest knowledge from pdf
prune hivemind
get intelligence stats
reflect on task`.split('\n');

const eqStr = fs.readFileSync('dashboard/src/lib/equations.ts', 'utf8');
const missing = [];

for (const raw of pasted) {
  if (!raw.trim()) continue;
  const key = raw.trim().replace(/ /g, '_');
  if (!eqStr.includes(`${key}: {`)) {
    missing.push(key);
  }
}

console.log("Missing:", missing);
