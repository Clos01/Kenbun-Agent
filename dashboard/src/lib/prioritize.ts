// Client-side port of scripts/prioritize_board.py's scoring model, so the
// board page can rank cards without a backend round-trip. Keep calculateCardScore
// numerically in lockstep with calculate_card_score() in the Python script — if
// one changes, change both.

export interface ScorableCard {
  id: string;
  listId: string;
  name: string;
  description?: string;
  dueDate?: string;
  isClosed?: boolean;
}

export interface ScorableList {
  id: string;
  name: string;
}

const CRITICAL = ["critical", "urgent", "blocker", "p0", "p1"];
const HIGH = ["high", "p2", "must-have"];
const HERO_EMOJI = ["🏆", "🔥", "⭐"];
const LOW = ["low", "nice-to-have", "p3", "optional"];
const DEP_HINTS = ["before", "depends on", "requires", "dependency"];

/** Mirror of calculate_card_score(card, list_name) in prioritize_board.py. */
export function calculateCardScore(card: ScorableCard, listName: string): number {
  let score = 0;

  const lname = (listName || "").toLowerCase();
  if (lname.includes("in progress")) score += 100;
  else if (lname.includes("blocked")) score += 80;
  else if (lname.includes("to do") || lname.includes("todo")) score += 50;
  else if (lname.includes("done") || lname.includes("completed")) score -= 500;

  if (card.dueDate) {
    const datePart = String(card.dueDate).split("T")[0];
    // Parse as local midnight to match the Python date() day-delta math.
    const due = new Date(`${datePart}T00:00:00`);
    if (!Number.isNaN(due.getTime())) {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const deltaDays = Math.round((due.getTime() - today.getTime()) / 86_400_000);
      if (deltaDays < 0) score += 200;
      else if (deltaDays === 0) score += 150;
      else if (deltaDays <= 3) score += 100;
      else if (deltaDays <= 7) score += 50;
    }
  }

  const name = (card.name || "").toLowerCase();
  const desc = (card.description || "").toLowerCase();
  const inEither = (kw: string) => name.includes(kw) || desc.includes(kw);

  if (CRITICAL.some(inEither)) score += 120;
  if (HIGH.some(inEither)) score += 60;
  if (HERO_EMOJI.some((kw) => name.includes(kw))) score += 80;
  if (LOW.some(inEither)) score -= 40;
  if (DEP_HINTS.some((kw) => desc.includes(kw))) score += 50;

  return score;
}

function isDoneList(listName: string): boolean {
  const n = (listName || "").toLowerCase();
  return n.includes("done") || n.includes("completed");
}

/**
 * Extract the dependency card ids a card declares in its kenbun_metadata
 * comment. Kept dependency-free (no import of the board parser) so this lib
 * stays self-contained; the shape mirrors parseCardMetadata's output.
 */
export function extractDependencies(description?: string): string[] {
  if (!description) return [];
  const m = /<!--\s*kenbun_metadata:\s*(\{[\s\S]*?\})\s*-->/.exec(description);
  if (!m) return [];
  try {
    const obj = JSON.parse(m[1]);
    const deps = obj && obj.dependencies;
    return Array.isArray(deps) ? deps.filter((d: unknown): d is string => typeof d === "string") : [];
  } catch {
    return [];
  }
}

export interface WorkOrder {
  /** cardId -> 1-based global rank among actionable cards (1 = do first). */
  rank: Map<string, number>;
  /** cardId -> raw priority score, for tooltips/debugging. */
  score: Map<string, number>;
  /** cardIds that are NOT dependency-ready (a predecessor is still open). */
  blocked: Set<string>;
  /** total number of actionable (ranked) cards. */
  total: number;
}

/**
 * Rank every open, non-done card into a single global work order.
 *
 * Dependency-readiness gate (first step of the WSJF/CPM engine tracked on the
 * Main Board): a card is "ready" only when every dependency it declares is
 * done/closed or absent from the board. READY cards always rank ahead of
 * blocked ones, so #1 is guaranteed to be something you can actually start —
 * within each group, ordering falls back to calculateCardScore.
 *
 * (calculateCardScore itself is unchanged and still mirrors
 * scripts/prioritize_board.py; only the ordering adds the readiness gate.)
 */
export function computeWorkOrder(cards: ScorableCard[], lists: ScorableList[]): WorkOrder {
  const listNameById = new Map(lists.map((l) => [l.id, l.name || "Unknown List"]));

  // Ids that count as "satisfied" for a dependency: closed, or sitting in a
  // done/completed list.
  const doneIds = new Set(
    cards
      .filter((c) => c.isClosed || isDoneList(listNameById.get(c.listId) || ""))
      .map((c) => c.id),
  );

  const active = cards.filter(
    (c) => !c.isClosed && !isDoneList(listNameById.get(c.listId) || ""),
  );
  const activeIds = new Set(active.map((c) => c.id));

  // A dependency only blocks if it points at an active card that isn't done.
  // Unknown ids (off-board / already-deleted) are treated as satisfied.
  const isReady = (c: ScorableCard) =>
    extractDependencies(c.description).every((d) => !activeIds.has(d) || doneIds.has(d));

  const blocked = new Set<string>();
  const scored = active.map((c) => {
    const ready = isReady(c);
    if (!ready) blocked.add(c.id);
    return {
      id: c.id,
      ready,
      score: calculateCardScore(c, listNameById.get(c.listId) || "Unknown List"),
    };
  });

  // Ready first, then by descending score; stable ties keep incoming order.
  scored.sort((a, b) => {
    if (a.ready !== b.ready) return a.ready ? -1 : 1;
    return b.score - a.score;
  });

  const rank = new Map<string, number>();
  const score = new Map<string, number>();
  scored.forEach((s, i) => {
    rank.set(s.id, i + 1);
    score.set(s.id, s.score);
  });

  return { rank, score, blocked, total: scored.length };
}
