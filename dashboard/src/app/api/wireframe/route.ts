import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

// Define the path to our wireframe JSON store
const wireframePath = path.join(process.cwd(), "src/data/wireframe.json");

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export async function OPTIONS() {
  return NextResponse.json({}, { headers: corsHeaders });
}

export async function GET() {
  try {
    if (!fs.existsSync(wireframePath)) {
      return NextResponse.json({ elements: [] }, { headers: corsHeaders });
    }
    const data = fs.readFileSync(wireframePath, "utf-8");
    return NextResponse.json(JSON.parse(data), { headers: corsHeaders });
  } catch (error) {
    console.error("Failed to read wireframe JSON:", error);
    return NextResponse.json({ error: "Failed to read wireframe data" }, { status: 500, headers: corsHeaders });
  }
}

export async function POST(request: Request) {
  try {
    const data = await request.json();
    
    // Ensure the data directory exists
    const dir = path.dirname(wireframePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    fs.writeFileSync(wireframePath, JSON.stringify(data, null, 2), "utf-8");
    return NextResponse.json({ success: true }, { headers: corsHeaders });
  } catch (error) {
    console.error("Failed to save wireframe JSON:", error);
    return NextResponse.json({ error: "Failed to save wireframe data" }, { status: 500, headers: corsHeaders });
  }
}
