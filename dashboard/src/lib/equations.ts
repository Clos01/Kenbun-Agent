export const TOOL_EQUATIONS: Record<string, { math: string; desc: string }> = {
  bayesian_governor: {
    math: `P(θ|D) ∝ P(D|θ)P(θ)

Beta(α₀=1, β₀=1)
λ = 0.5^(age_hours / 24)
α = 1 + success_count·λ
β = 1 + failure_count·λ
P(success) = α / (α + β)`,
    desc: "Beta-Bernoulli conjugate prior with a 24h recency half-life. Displayed weights are rebuilt from raw event counts, not the stored alpha/beta columns."
  },
  token_governor: {
    math: `E_t = λx_t + (1-λ)E_{t-1}

∀t: C_{total} ≤ B_{max}`,
    desc: "Exponential Moving Average (EMA) for burn rate prediction and hard ceiling budgeting."
  },
  topology_mapper: {
    math: `v_i = emb(c_i)

p_{2D} = UMAP(v_i)
x_{norm} = 50(tanh(x_{raw})+1)`,
    desc: "Non-linear dimensionality reduction and bounded topological projection."
  },
  audit_supervisor: {
    math: `C = (1/N) ∑_{i=1}^N 1(v_i ≥ τ)`,
    desc: "Discrete multi-model consensus verification thresholding."
  },
  neural_classifier: {
    math: `ŷ = mode{h_1(x), h_2(x), ..., h_K(x)}`,
    desc: "Random Forest ensemble mode aggregation across K decision trees."
  },
  intelligence_engine: {
    math: `ΔW_{ij} = -η (∂E/∂W_{ij}) + μΔW_{ij}^{(t-1)}`,
    desc: "Gradient descent with momentum for weight optimization."
  },
  vector_sync_worker: {
    math: `S_C(A, B) = (A · B) / (||A|| ||B||) = ∑ A_i B_i / (√(∑ A_i^2) √(∑ B_i^2))`,
    desc: "Cosine similarity calculation for semantic embedding proximity."
  },
  orchestrate: {
    math: `T_{exec} = max(T_1, T_2, ..., T_k) + O(N)`,
    desc: "Parallel pipeline concurrency bound and overhead resolution."
  },
  ask_ui_expert: {
    math: `ΔE_{00}^* = √((ΔL' / k_L S_L)^2 + (ΔC' / k_C S_C)^2 + (ΔH' / k_H S_H)^2)`,
    desc: "CIEDE2000 color difference formula for strict Blueprint palette matching."
  },
  memory_classifier: {
    math: `D_{KL}(P||Q) = ∑_{x ∈ X} P(x) log(P(x)/Q(x))`,
    desc: "Kullback-Leibler divergence for context distribution entropy reduction."
  },
  sovereignty_engine: {
    math: `Φ = ∀x ∈ AST: f_{rule}(x) ≡ True`,
    desc: "Formal deterministic verification of Abstract Syntax Tree constraints."
  },
  get_brain_health: {
    math: `H = α(1 - U_{cpu}/100) + β(M_{free}/M_{total}) + γ(1 / (1 + L_{avg}))`,
    desc: "Weighted sum heuristic for swarm orchestrator health."
  },
  guardrail_audit: {
    math: `P(x ∈ Safe) = 1 - ∏_{i=1}^N (1 - P(f_i(x) = Violation))`,
    desc: "Deterministic AST boundary checks and static regex pattern matching."
  },
  audit_guardrail: {
    math: `P(x ∈ Safe) = 1 - ∏_{i=1}^N (1 - P(f_i(x) = Violation))`,
    desc: "Deterministic AST boundary checks and static regex pattern matching."
  },
  telemetry_pulse: {
    math: `f_{hz} = 1 / Δt_{cycle}

S_{avg} = (1/T) ∫_{0}^{T} s(t) dt`,
    desc: "High-frequency polling delta and signal integration over time."
  },
  fleet_monitor: {
    math: `L_{node} = t_{ack} - t_{syn}

H(node) = 1(L_{node} < τ_{max})`,
    desc: "Network latency measurement and discrete boolean health thresholding."
  },
  background_sync: {
    math: `J_t = (J_{t-1} \cup {j_{new}}) \setminus {j_{done}}`,
    desc: "Set-theoretic union and difference for atomic job queue processing."
  },
  scan_repo: {
    math: `O(V + E) \text{ where } V = |Files|, E = |Dependencies|`,
    desc: "Graph traversal time complexity for breadth-first repository scanning."
  },
  run_code_safely: {
    math: `E[R] = \int_{Sandbox} r(x) P(x) dx`,
    desc: "Expected isolated return value of sandboxed stochastic code execution."
  },
  list_checkpoints: {
    math: `C_{t} = SHA256(State_t \parallel C_{t-1})`,
    desc: "Cryptographic hash chaining of chronological state snapshots."
  },
  index_codebase: {
    math: `E_{doc} = \frac{1}{|Tokens|} \sum_{i=1}^{|Tokens|} emb(w_i)`,
    desc: "Mean pooling of sub-word token embeddings for aggregate document vectors."
  },
  delete_from_hivemind: {
    math: `V_{new} = V_{old} \setminus \{v_k \mid d(v_k, q) < \epsilon\}`,
    desc: "Vector excision based on epsilon-ball proximity culling."
  },
  audit_package_safety: {
    math: `R_{pkg} = w_1(CVE) + w_2(Age) + w_3(Downloads)`,
    desc: "Weighted risk scoring for external supply-chain dependencies."
  },
  ask_architect: {
    math: `A_{score} = \max_{p \in Patterns} Sim(p, Query)`,
    desc: "Argmax similarity retrieval against known structural design principles."
  },
  consult_supervisor: {
    math: `Decision = mode(LLM_1(x), LLM_2(x), Rule(x))`,
    desc: "Majority-vote consensus fallback across heterogeneous models."
  },
  autofix_linter: {
    math: `AST' = f_{transform}(AST) \text{ s.t. } Linter(AST') = 0`,
    desc: "Greedy heuristic transformation targeting zero remaining diagnostic errors."
  },
  research_official_docs: {
    math: `tf-idf(t, d, D) = f_{t,d} \cdot \log \frac{|D|}{|\{d \in D : t \in d\}|}`,
    desc: "Term frequency-inverse document frequency weighting for documentation retrieval."
  },
  review_code_with_gemini: {
    math: `P_{bug}(L) = \sigma(W \cdot emb(L) + b)`,
    desc: "Sigmoid probability of logical bugs mapped directly from contextual code embeddings."
  },
  research_with_gemini: {
    math: `K_{new} = K_{old} \cup \{ (q, a) \}`,
    desc: "Monotonic knowledge expansion mapping unstructured text to factual pairs."
  },
  remember_fix: {
    math: `M_{t} = alpha M_{t-1} + (1 - alpha) Delta Fix`,
    desc: "Exponential decay weighting prioritizing recent chronological bug fixes."
  },
  recall_fix: {
    math: `argmin_k ||v_{error} - v_{fix_k}||_2`,
    desc: "L2 Euclidean distance minimization for historical bug signature retrieval."
  },
  save_checkpoint: {
    math: `\Delta = |State_t - State_{t-1}|`,
    desc: "Diff magnitude computation isolating chronological file modifications."
  },
  restore_checkpoint: {
    math: `State_t = State_{t-k} \text{ s.t. } t-k \ge 0`,
    desc: "Absolute state reversal and rollback via pointer realignment."
  },
  save_to_hivemind: {
    math: `H = H \cup Compress(Plan_{success})`,
    desc: "Lossy compression and long-term integration of successful agent plans."
  },
  search_hivemind_concepts: {
    math: `top_k = argmax_{C \subset H, |C|=k} \sum_{c \in C} Cosine(q, c)`,
    desc: "K-nearest neighbor extraction over the persistent concept manifold."
  },
  search_codebase: {
    math: `Rel(d, q) = w_{bm25} BM25(d, q) + w_{vec} Cosine(v_d, v_q)`,
    desc: "Hybrid BM25 keyword and dense vector semantic retrieval."
  },
  think_about_tools: {
    math: `UCB_j = \mu_j + C \sqrt{\frac{2 \ln n}{n_j}}`,
    desc: "Upper Confidence Bound calculation for multi-armed bandit routing."
  },
  patch_hivemind_concept: {
    math: `v_{new} = v_{old} + \eta \nabla L(v_{old})`,
    desc: "Iterative delta application refining local concept boundaries."
  },
  ingest_knowledge_from_pdf: {
    math: `C = \{c_1, c_2, ..., c_n\} \text{ s.t. } |c_i| \le Token_{max}`,
    desc: "Discrete semantic chunking algorithm constrained by context window limits."
  },
  prune_hivemind: {
    math: `H' = H \setminus \{ c \in H \mid Utility(c) < \theta \}`,
    desc: "Stochastic pruning of low-utility or rarely-accessed memory nodes."
  },
  get_intelligence_stats: {
    math: `S_{agg} = \frac{1}{|T|} \sum_{t \in T} stats(t)`,
    desc: "Global aggregation mean covering the entire multi-agent hierarchy."
  },
  reflect_on_task: {
    math: `R = Evaluate(Checklist, Output) \rightarrow \{0, 1\}^N`,
    desc: "Binary classification vector assessing deterministic checklist completion."
  },
  reflect: {
    math: `Q(s,a) = R(s,a) + γ max Q(s',a')`,
    desc: "Bellman equation for Q-learning state evaluation during trajectory reflection."
  },
  gemini_review: {
    math: `P_{bug}(C) = softmax(W_{rev} · emb(C) / √d)`,
    desc: "Scaled dot-product attention over code embeddings for vulnerability detection."
  },
  get_design_tokens: {
    math: `T = { c_i ∈ CSS_AST | type(c_i) = :root }`,
    desc: "AST traversal to extract root-level global CSS custom properties."
  },
  remember_result: {
    math: `Cache(k) = v, LRU_{update}(k) -> O(1)`,
    desc: "Constant-time dictionary insertion with Least Recently Used eviction tracking."
  },
  research: {
    math: `Score(q, d) = ∑_{w ∈ q} IDF(w) \frac{f(w,d)(k+1)}{f(w,d) + k(1-b + b \frac{|d|}{avgdl})}`,
    desc: "Okapi BM25 ranking function for robust information retrieval."
  },
  supervisor_review: {
    math: `E[U] = ∑ P(outcome|a) U(outcome)`,
    desc: "Expected Utility calculation weighting the safety and correctness of proposals."
  },
  supervisor_audit: {
    math: `V = ∏_{i=1}^N \mathbb{1}(Rule_i(x) = True) \implies \{0, 1\}`,
    desc: "Strict boolean product across N discrete validation boundaries."
  },
  read_file: {
    math: `Chunks = ⌈ \frac{Bytes}{TokenRatio \cdot W_{max}} ⌉`,
    desc: "Deterministic sliding window chunking to satisfy strict LLM context limits."
  }
};
