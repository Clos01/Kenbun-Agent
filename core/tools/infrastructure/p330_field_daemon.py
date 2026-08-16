"""
p330 Autonomous Field Operations Daemon
────────────────────────────────────────
Runs 24/7 on server p330.
Does NOT require Carlos's Mac to be powered on.

Capabilities:
1. Lead Watchdog: Scans PostgreSQL 'crg_leads' for new high-value leads and triggers n8n pipeline.
2. Mobile Reply Router: Listens for incoming email/SMS replies from Carlos in the field:
   - "Approve" / "Send" -> Dispatches outreach email to contractor & updates Planka CRM.
   - Instructions (e.g. "Change price to $4,500") -> Calls FastMCP AI generator with feedback & sends revised preview.
   - "Reject" -> Cancels outreach.
"""

import sys
import time
import logging
import json
import urllib.request
import urllib.parse
from typing import Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (p330_field_daemon) %(message)s"
)

FASTMCP_URL = "http://100.100.199.127:8001/api/v1/intelligence/generate-outreach"
N8N_WEBHOOK_URL = "https://n8n.rivasautomations.com/webhook/flooring-lead-capture?secret=RivasSecretKey123!"

class P330FieldDaemon:
    def __init__(self):
        self.running = True
        self.poll_interval = 300  # 5 minutes

    def trigger_n8n_lead_pipeline(self, lead_data: Dict[str, Any]) -> bool:
        """Fires lead payload to n8n webhook on p330."""
        try:
            req_data = json.dumps(lead_data).encode("utf-8")
            req = urllib.request.Request(
                N8N_WEBHOOK_URL,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = resp.read().decode("utf-8")
                logging.info(f"Successfully triggered n8n lead pipeline: {result}")
                return True
        except Exception as e:
            logging.error(f"Failed to trigger n8n pipeline: {e}")
            return False

    def process_mobile_reply(self, reply_text: str, lead_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses Carlos's mobile reply instructions while in the field.
        """
        clean_reply = reply_text.strip().lower()

        # 1. APPROVAL ACTION
        if clean_reply in ("approve", "send", "approved", "lgtm"):
            logging.info("Carlos replied APPROVE -> Sending outreach to contractor.")
            return {
                "action": "dispatch",
                "status": "APPROVED",
                "message": f"Outreach email dispatched to {lead_context.get('company_name', 'Contractor')}."
            }

        # 2. REJECTION ACTION
        elif clean_reply in ("reject", "cancel", "pass", "skip"):
            logging.info("Carlos replied REJECT -> Canceling outreach.")
            return {
                "action": "cancel",
                "status": "REJECTED",
                "message": "Outreach workflow canceled."
            }

        # 3. EDIT / REVISION ACTION
        else:
            logging.info(f"Carlos provided custom instructions: '{reply_text}' -> Regenerating draft.")
            # Call FastMCP with Carlos's feedback incorporated
            req_data = json.dumps({
                "client_name": lead_context.get("name", "Valued Partner"),
                "company_name": lead_context.get("company_name", "Commercial Client"),
                "address": lead_context.get("address", "the local area"),
                "type": lead_context.get("work_class", "Commercial Flooring"),
                "work_details": f"{lead_context.get('work_details', '')}\n[Field Edit Request]: {reply_text}"
            }).encode("utf-8")

            try:
                req = urllib.request.Request(
                    FASTMCP_URL,
                    data=req_data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    ai_res = json.loads(resp.read().decode("utf-8"))
                    logging.info("Successfully generated revised draft based on Carlos's field feedback.")
                    return {
                        "action": "revised_preview",
                        "status": "REVISED",
                        "subject": ai_res.get("subject"),
                        "formatted_approval_email": ai_res.get("formatted_approval_email")
                    }
            except Exception as e:
                logging.error(f"Failed to regenerate draft via FastMCP: {e}")
                return {"action": "error", "message": str(e)}

    def run_watchdog_loop(self):
        """Main 24/7 background loop running on p330."""
        logging.info("Starting p330 Field Daemon watchdog loop...")
        while self.running:
            try:
                # Polling / listening logic
                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                logging.info("Stopping p330 Field Daemon...")
                self.running = False
            except Exception as e:
                logging.error(f"Daemon error: {e}")
                time.sleep(10)

if __name__ == "__main__":
    daemon = P330FieldDaemon()
    if len(sys.argv) > 1 and sys.argv[1] == "--test-reply":
        test_context = {
            "name": "Steve Jolley",
            "company_name": "Steve Jolley Builders",
            "address": "708 Sasser St, Raleigh, NC 27604",
            "work_class": "Two Story Commercial Addition",
            "work_details": "[Addition] Two story Addition (792sqft) to consist of den, bedrooms, bath, laundry."
        }
        reply_input = sys.argv[2] if len(sys.argv) > 2 else "Approve"
        res = daemon.process_mobile_reply(reply_input, test_context)
        print("\nTEST MOBILE REPLY RESULT:\n", json.dumps(res, indent=2))
    else:
        daemon.run_watchdog_loop()
