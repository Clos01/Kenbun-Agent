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

export interface WorkOrder {
  /** cardId -> 1-based global rank among actionable cards (1 = do first). */
  rank: Map<string, number>;
  /** cardId -> raw priority score, for tooltips/debugging. */
  score: Map<string, number>;
  /** total number of actionable (ranked) cards. */
  total: number;
}

/**
 * Rank every open, non-done card into a single global work order.
 * Done/completed and closed cards are excluded so the badges read 1..N over
 * the cards you'd actually pick up next.
 */
export function computeWorkOrder(cards: ScorableCard[], lists: ScorableList[]): WorkOrder {
  const listNameById = new Map(lists.map((l) => [l.id, l.name || "Unknown List"]));

  const scored = cards
    .filter((c) => {
      if (c.isClosed) return false;
      return !isDoneList(listNameById.get(c.listId) || "");
    })
    .map((c) => ({
      id: c.id,
      score: calculateCardScore(c, listNameById.get(c.listId) || "Unknown List"),
    }));

  // Descending score; stable ties keep the incoming (Planka position) order.
  scored.sort((a, b) => b.score - a.score);

  const rank = new Map<string, number>();
  const score = new Map<string, number>();
  scored.forEach((s, i) => {
    rank.set(s.id, i + 1);
    score.set(s.id, s.score);
  });

  return { rank, score, total: scored.length };
}
