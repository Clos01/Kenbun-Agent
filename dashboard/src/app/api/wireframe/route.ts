import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

/**
 * Wireframe storage, scoped per project.
 *
 * This route used to read and write a SINGLE global file, src/data/wireframe.json.
 * That meant there was only ever one wireframe in the whole system: generating for
 * one project silently destroyed another project's, and every project's board
 * displayed whatever had been generated last, no matter which app it belonged to.
 *
 * Wireframes are now keyed by Planka project id, matching how per-project SOWs are
 * stored (`sows` table, /api/v1/sow?project_id=), so the two features agree on what
 * "a project" means.
 */

const dataDir = path.join(process.cwd(), "src/data");
const wireframeDir = path.join(dataDir, "wireframes");
const legacyPath = path.join(dataDir, "wireframe.json");

/**
 * Parked home for the pre-scoping wireframe.
 *
 * The filename deliberately contains a "." — a character no valid project_id can
 * contain (see projectFile below) — so this file is UNADDRESSABLE through the API
 * by construction. An earlier version parked it at "_unassigned.json", which does
 * match the id charset, so `?project_id=_unassigned` served it to anyone who
 * guessed the name. Making it structurally unreachable is stronger than adding it
 * to a blocklist, which is only ever as good as the list.
 */
const legacyParkedPath = path.join(wireframeDir, "legacy.unassigned.json");
const oldParkedPath = path.join(wireframeDir, "_unassigned.json");

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

const EMPTY_SCENE = { type: "excalidraw", version: 2, elements: [], appState: {} };

/**
 * Project ids come from Planka and are numeric strings. Validate rather than
 * sanitise: a project id that does not look like one is a caller bug, and quietly
 * rewriting it would map two different callers onto the same file — the exact
 * cross-project bleed this route exists to prevent. Also blocks path traversal,
 * since this value becomes a filename.
 *
 * Note the charset excludes "." — that is load-bearing, not incidental. It is what
 * makes any file whose name contains a dot (see legacyParkedPath) impossible to
 * reach through this API, and it independently rules out traversal, extensions and
 * hidden files.
 */
function projectFile(projectId: string): string | null {
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(projectId)) return null;
  const file = path.join(wireframeDir, `${projectId}.json`);
  // Defence in depth: even with the charset check, never hand back a path that
  // escaped the intended directory.
  if (path.dirname(path.resolve(file)) !== path.resolve(wireframeDir)) return null;
  return file;
}

function migrateLegacy(): void {
  fs.mkdirSync(wireframeDir, { recursive: true });

  // Relocate anything parked under the old, guessable name.
  if (fs.existsSync(oldParkedPath)) {
    if (!fs.existsSync(legacyParkedPath)) fs.renameSync(oldParkedPath, legacyParkedPath);
    else fs.rmSync(oldParkedPath);
  }

  // Preserve the pre-scoping wireframe rather than orphaning it. It belongs to no
  // project, so it is parked out of reach rather than assigned to one by guesswork.
  if (!fs.existsSync(legacyPath)) return;
  if (fs.existsSync(legacyParkedPath)) return;
  fs.copyFileSync(legacyPath, legacyParkedPath);
}

export async function OPTIONS() {
  return NextResponse.json({}, { headers: corsHeaders });
}

export async function GET(request: Request) {
  try {
    const projectId = new URL(request.url).searchParams.get("project_id");
    if (!projectId) {
      return NextResponse.json(
        { error: "project_id is required. A wireframe belongs to exactly one project." },
        { status: 400, headers: corsHeaders },
      );
    }
    const file = projectFile(projectId);
    if (!file) {
      return NextResponse.json(
        { error: "Invalid project_id." },
        { status: 400, headers: corsHeaders },
      );
    }

    migrateLegacy();

    if (!fs.existsSync(file)) {
      // No wireframe for THIS project yet. Return an empty scene rather than
      // falling back to any other project's — an empty canvas is the honest
      // answer, and a fallback is how cross-project bleed gets reintroduced.
      return NextResponse.json(EMPTY_SCENE, { headers: corsHeaders });
    }
    return NextResponse.json(JSON.parse(fs.readFileSync(file, "utf-8")), {
      headers: corsHeaders,
    });
  } catch (error) {
    console.error("Failed to read wireframe JSON:", error);
    return NextResponse.json(
      { error: "Failed to read wireframe data" },
      { status: 500, headers: corsHeaders },
    );
  }
}

export async function POST(request: Request) {
  try {
    const url = new URL(request.url);
    const data = await request.json();
    // Accept the id from the query string or the body so the MCP tool can post a
    // plain scene object with ?project_id=, and the canvas can post either way.
    const projectId = url.searchParams.get("project_id") || data?.project_id;

    if (!projectId) {
      return NextResponse.json(
        { error: "project_id is required so the wireframe is attached to one project." },
        { status: 400, headers: corsHeaders },
      );
    }
    const file = projectFile(String(projectId));
    if (!file) {
      return NextResponse.json(
        { error: "Invalid project_id." },
        { status: 400, headers: corsHeaders },
      );
    }

    fs.mkdirSync(wireframeDir, { recursive: true });
    migrateLegacy();

    const scene = { ...data };
    delete scene.project_id; // routing metadata, not part of the scene
    scene.projectId = String(projectId); // stamped so an exported file is traceable

    fs.writeFileSync(file, JSON.stringify(scene, null, 2), "utf-8");
    return NextResponse.json(
      { success: true, project_id: String(projectId) },
      { headers: corsHeaders },
    );
  } catch (error) {
    console.error("Failed to save wireframe JSON:", error);
    return NextResponse.json(
      { error: "Failed to save wireframe data" },
      { status: 500, headers: corsHeaders },
    );
  }
}
