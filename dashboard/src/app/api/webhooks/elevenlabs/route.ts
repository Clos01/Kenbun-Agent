import { NextResponse } from "next/server";

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    
    console.log("[ElevenLabs Webhook] Received payload:", payload);

    // TODO: Verify webhook signature/token from headers
    // const authHeader = request.headers.get("authorization");
    
    // TODO: Parse the payload according to ElevenLabs webhook documentation
    const { call_id, agent_id, status, transcript, recording_url } = payload;
    void call_id; void agent_id; void status; void transcript; void recording_url;

    // TODO: Insert or update the Call record in Supabase
    /*
    const { data, error } = await supabase
      .from('call')
      .upsert({
        id: call_id,
        agent_id,
        transcript,
        recording_url,
        outcome: status
      });
    */

    return NextResponse.json({ success: true, message: "Webhook processed" });
  } catch (error) {
    console.error("[ElevenLabs Webhook] Error processing webhook:", error);
    return NextResponse.json({ success: false, error: "Internal Server Error" }, { status: 500 });
  }
}
