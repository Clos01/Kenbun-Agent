import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function GET() {
  try {
    const projectRoot = path.resolve(process.cwd(), "..");
    const brainHealthSessions = path.join(projectRoot, "brain_health", "adw_sessions");
    const homeSessions = path.join(process.env.HOME || "", ".kenbun", "adw_sessions");

    let sessionsDir = brainHealthSessions;
    if (!fs.existsSync(sessionsDir) && fs.existsSync(homeSessions)) {
      sessionsDir = homeSessions;
    }

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const workflows: any[] = [];

    if (fs.existsSync(sessionsDir)) {
      const entries = fs.readdirSync(sessionsDir, { withFileTypes: true });

      for (const entry of entries) {
        if (entry.isDirectory()) {
          const taskDir = path.join(sessionsDir, entry.name);
          const manifestPath = path.join(taskDir, "workflow_manifest.json");

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
          let manifest: any = {
            task_id: entry.name,
            last_updated: new Date().toISOString(),
            phases: {}
          };

          if (fs.existsSync(manifestPath)) {
            try {
              manifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
            } catch (err) {
              console.error("Error reading manifest:", err);
            }
          }

          // Scan for any envelope_*.json files in this folder
          const files = fs.readdirSync(taskDir);
          const phaseFiles = files.filter(f => f.startsWith("envelope_") && f.endsWith(".json"));
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const envelopes: Record<string, any> = {};

          for (const pFile of phaseFiles) {
            const phaseName = pFile.replace("envelope_", "").replace(".json", "");
            try {
              const envData = JSON.parse(fs.readFileSync(path.join(taskDir, pFile), "utf-8"));
              envelopes[phaseName] = envData;
              if (!manifest.phases[phaseName]) {
                manifest.phases[phaseName] = {
                  status: envData.status || "completed",
                  model: envData.model_name || "claude-sonnet-5",
                  timestamp: envData.timestamp || new Date().toISOString(),
                  summary: envData.plan_summary || ""
                };
              }
            } catch (err) {
              console.error("Error parsing envelope:", err);
            }
          }

          workflows.push({
            ...manifest,
            envelopes
          });
        }
      }
    }

    // Sort newest first
    workflows.sort((a, b) => new Date(b.last_updated || 0).getTime() - new Date(a.last_updated || 0).getTime());

    // If no workflows exist yet, provide seed demo workflows
    if (workflows.length === 0) {
      workflows.push({
        task_id: "adw_demo_sssf",
        last_updated: new Date().toISOString(),
        phases: {
          scout: {
            status: "completed",
            model: "gemini-2.0-flash",
            timestamp: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
            summary: "Scouted reverse proxy and authentication endpoints across all 3 cluster nodes."
          },
          plan: {
            status: "completed",
            model: "claude-sonnet-5",
            timestamp: new Date(Date.now() - 1000 * 60 * 8).toISOString(),
            summary: "Designed strict JSON context envelope & deterministic test-pass token gate."
          },
          build: {
            status: "completed",
            model: "claude-sonnet-5",
            timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
            summary: "Implemented envelope.py and Next.js visual swimlane component."
          },
          test: {
            status: "completed",
            model: "deterministic-gate",
            timestamp: new Date(Date.now() - 1000 * 60 * 2).toISOString(),
            summary: "Verified unit test assertions (100% pass; stdout suppressed)."
          },
          review: {
            status: "completed",
            model: "claude-sonnet-5",
            timestamp: new Date().toISOString(),
            summary: "System 2 Supervisor signed off on multi-agent safety compliance."
          }
        },
        envelopes: {
          plan: {
            task_id: "adw_demo_sssf",
            phase: "plan",
            model_name: "claude-sonnet-5",
            plan_summary: "Designed strict JSON context envelope & deterministic test-pass token gate.",
            target_files: ["core/tools/strategy/envelope.py", "core/tools/execution/e2b_runner.py"],
            required_tests: ["test_envelope_validation", "test_deterministic_pass_filter"],
            handoff_notes: "Keep mkcert wildcard TLS untouched. Validate on both host & container.",
            token_stats: {
              input_tokens: 1420,
              output_tokens: 680,
              total_tokens: 2100,
              estimated_cost_usd: 0.014
            },
            status: "completed"
          }
        }
      });
    }

    return NextResponse.json({
      success: true,
      count: workflows.length,
      workflows
    });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 }
    );
  }
}
