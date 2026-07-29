import { NextRequest, NextResponse } from "next/server";

/**
 * SOW → Work Breakdown Structure decomposer.
 *
 * Project-driven (no hardcoded NeverMiss content): it decomposes the SELECTED
 * project's SOW epics into a WBS scoped to that project's board/list. The caller
 * must pass the target board/list — there is no default board.
 *
 * Story points are estimated from the epic detail length as a lightweight heuristic
 * until an LLM estimator is wired. Planka push is intentionally NOT faked here:
 * card creation must go through the authenticated backend planka router.
 */

interface InEpic { id?: number | string; title?: string; details?: string; description?: string; }

function estimatePoints(text: string): number {
  const len = (text || "").trim().length;
  if (len === 0) return 1;
  if (len < 120) return 2;
  if (len < 300) return 3;
  if (len < 600) return 5;
  return 8;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      epics = [],
      boardId = "",
      targetListId = "",
      pushToPlanka = false,
    }: { epics?: InEpic[]; boardId?: string; targetListId?: string; pushToPlanka?: boolean } = body;

    if (!boardId || !targetListId) {
      return NextResponse.json(
        { error: "boardId and targetListId are required — the decomposer is scoped to the selected project's board." },
        { status: 400 }
      );
    }

    if (!Array.isArray(epics) || epics.length === 0) {
      return NextResponse.json(
        { success: true, summary: { totalEpics: 0, totalTasks: 0, totalStoryPoints: 0, estimatedSprintWeeks: 0, plankaSyncResult: "No epics to decompose." }, epics: [] }
      );
    }

    // Transform this project's SOW epics into a WBS scoped to its board/list.
    const wbs = epics.map((e, idx) => {
      const detail = e.details || e.description || "";
      return {
        id: `EPIC-${idx + 1}`,
        title: e.title || `Epic ${idx + 1}`,
        description: detail,
        tasks: [
          {
            title: e.title || `Epic ${idx + 1}`,
            points: estimatePoints(detail),
            criteria: detail || "Define acceptance criteria.",
            plankaListId: targetListId,
            plankaBoardId: boardId,
          },
        ],
      };
    });

    const totalStoryPoints = wbs.reduce(
      (sum, epic) => sum + epic.tasks.reduce((t, task) => t + task.points, 0),
      0
    );

    // Honest status: we do not fake a Planka sync. Real card creation must go
    // through the authenticated backend planka router (POST /api/v1/planka/cards).
    const plankaSyncResult = pushToPlanka
      ? "Push requested — create cards via the authenticated /api/v1/planka/cards endpoint (not performed here)."
      : "Decomposition ready for review.";

    return NextResponse.json({
      success: true,
      summary: {
        totalEpics: wbs.length,
        totalTasks: wbs.reduce((sum, epic) => sum + epic.tasks.length, 0),
        totalStoryPoints,
        estimatedSprintWeeks: Math.ceil(totalStoryPoints / 10),
        boardId,
        targetListId,
        plankaSyncResult,
      },
      epics: wbs,
    });
  } catch (error) {
    const msg = error instanceof Error ? error.message : "Decomposition failed";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
