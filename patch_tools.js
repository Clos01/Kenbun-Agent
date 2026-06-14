const fs = require('fs');

const missingTools = {
  reflect: {
    system: "System 5 (Reflection)",
    role: "Internal State Evaluator",
    desc: "Evaluates intermediate agent traces to detect loops, hallucinations, or dead-ends, issuing corrective sub-goals if necessary."
  },
  gemini_review: {
    system: "System 1/2 (Cloud Execution)",
    role: "Cloud LLM Code Auditor",
    desc: "A dedicated endpoint for passing structural codebase changes to Gemini for deep static analysis and architectural feedback."
  },
  get_design_tokens: {
    system: "System 5 (Design Discovery)",
    role: "Aesthetic Variables Retriever",
    desc: "Extracts and parses raw CSS tokens, typography families, and color maps from the project's DESIGN.md or stylesheet."
  },
  remember_result: {
    system: "System 3 (Memory)",
    role: "Ephemeral Cache Syncer",
    desc: "Records the deterministic outputs of costly operations into a fast-access short-term memory layer to prevent redundant re-computation."
  },
  research: {
    system: "System 1 (Execution)",
    role: "Semantic Web/Code Crawler",
    desc: "Executes generalized searches across local file contexts and remote documentation to gather sufficient context for a given task."
  },
  supervisor_review: {
    system: "System 2 (Reasoning & Ethics)",
    role: "High-Level Executive Reviewer",
    desc: "Runs multi-stage review passes over major architectural proposals to ensure alignment with scalability and global design rules."
  },
  supervisor_audit: {
    system: "System 2 (Reasoning & Ethics)",
    role: "Strict Boundary Gatekeeper",
    desc: "Performs final strict validation checks on system commits and critical actions, terminating unsafe or unauthorized modifications."
  },
  read_file: {
    system: "System 1 (Execution)",
    role: "Direct Filesystem Reader",
    desc: "Provides raw, deterministic read access to the local filesystem, chunking large files if they exceed context window constraints."
  }
};

const missingEquations = {
  reflect: {
    math: "Q(s,a) = R(s,a) + γ max Q(s',a')",
    desc: "Bellman equation for Q-learning state evaluation during trajectory reflection."
  },
  gemini_review: {
    math: "P_{bug}(C) = softmax(W_{rev} · emb(C) / √d)",
    desc: "Scaled dot-product attention over code embeddings for vulnerability detection."
  },
  get_design_tokens: {
    math: "T = { c_i ∈ CSS_AST | type(c_i) = :root }",
    desc: "AST traversal to extract root-level global CSS custom properties."
  },
  remember_result: {
    math: "Cache(k) = v, LRU_{update}(k) -> O(1)",
    desc: "Constant-time dictionary insertion with Least Recently Used eviction tracking."
  },
  research: {
    math: "Score(q, d) = ∑_{w ∈ q} IDF(w) \\frac{f(w,d)(k+1)}{f(w,d) + k(1-b + b \\frac{|d|}{avgdl})}",
    desc: "Okapi BM25 ranking function for robust information retrieval."
  },
  supervisor_review: {
    math: "E[U] = ∑ P(outcome|a) U(outcome)",
    desc: "Expected Utility calculation weighting the safety and correctness of proposals."
  },
  supervisor_audit: {
    math: "V = ∏_{i=1}^N \\mathbb{1}(Rule_i(x) = True) \\implies \\{0, 1\\}",
    desc: "Strict boolean product across N discrete validation boundaries."
  },
  read_file: {
    math: "Chunks = ⌈ \\frac{Bytes}{TokenRatio \\cdot W_{max}} ⌉",
    desc: "Deterministic sliding window chunking to satisfy strict LLM context limits."
  }
};

// Update tools.ts
let toolsCode = fs.readFileSync('dashboard/src/lib/tools.ts', 'utf8');
let toolsInjection = '';
for (const [key, val] of Object.entries(missingTools)) {
  toolsInjection += `,\n  ${key}: {\n    system: "${val.system}",\n    role: "${val.role}",\n    desc: "${val.desc}"\n  }`;
}
toolsCode = toolsCode.replace(/\s*\}\s*;\s*\/\*\*/, toolsInjection + '\n};\n\n/**');
fs.writeFileSync('dashboard/src/lib/tools.ts', toolsCode);

// Update equations.ts
let eqCode = fs.readFileSync('dashboard/src/lib/equations.ts', 'utf8');
let eqInjection = '';
for (const [key, val] of Object.entries(missingEquations)) {
  eqInjection += `,\n  ${key}: {\n    math: \`${val.math}\`,\n    desc: "${val.desc}"\n  }`;
}
eqCode = eqCode.replace(/\s*\}\s*;\s*$/, eqInjection + '\n};\n');
fs.writeFileSync('dashboard/src/lib/equations.ts', eqCode);

console.log("Patched completely.");
