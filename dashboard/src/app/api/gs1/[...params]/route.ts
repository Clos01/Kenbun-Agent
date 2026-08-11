import { NextRequest, NextResponse } from "next/server";

interface GS1Rule {
  gtin: string;
  lot?: string;
  isRecalled: boolean;
  recallReason?: string;
  targetUrl: string;
  leadCaptureEnabled?: boolean;
}

const RESOLUTION_DATABASE: Record<string, GS1Rule> = {
  // Sample Product (Starry Soda / CPG Product)
  "00614141000036": {
    gtin: "00614141000036",
    isRecalled: false,
    targetUrl: "https://starrysoda.com/promo",
  },
  // Sample Recalled Lot (Infant Formula / Peanut Butter case study)
  "00614141000036:LOT99": {
    gtin: "00614141000036",
    lot: "LOT99",
    isRecalled: true,
    recallReason: "FDA Safety Alert: Potential bacterial contamination detected in Lot 99. Do not consume.",
    targetUrl: "https://fda.gov/recalls/alert-99",
  },
  // Flooring Sample Board (Lead Arbitrage Engine Integration)
  "00850012345678:SAMPLE-HARDWOOD": {
    gtin: "00850012345678",
    lot: "SAMPLE-HARDWOOD",
    isRecalled: false,
    leadCaptureEnabled: true,
    targetUrl: "http://100.92.127.1:3000/board",
  }
};

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ params?: string[] }> }
) {
  const resolvedParams = await context.params;
  const pathParams = resolvedParams.params || [];
  
  // Parse GS1 Key-Value Pairs
  let gtin = "";
  let lot = "";
  let serial = "";

  for (let i = 0; i < pathParams.length; i++) {
    if (pathParams[i] === "01" && pathParams[i + 1]) {
      gtin = pathParams[i + 1];
      i++;
    } else if (pathParams[i] === "10" && pathParams[i + 1]) {
      lot = pathParams[i + 1];
      i++;
    } else if (pathParams[i] === "21" && pathParams[i + 1]) {
      serial = pathParams[i + 1];
      i++;
    }
  }

  if (!gtin) {
    return NextResponse.json(
      { error: "Invalid GS1 Digital Link. Missing Application Identifier 01 (GTIN)." },
      { status: 400 }
    );
  }

  // Lookup resolution rules
  const lotKey = lot ? `${gtin}:${lot}` : gtin;
  const rule = RESOLUTION_DATABASE[lotKey] || RESOLUTION_DATABASE[gtin];

  if (!rule) {
    return NextResponse.json({
      status: "unregistered",
      gtin,
      lot: lot || null,
      message: "GS1 Digital Link valid but target brand URL not registered on resolver.",
      defaultUrl: `https://www.google.com/search?q=GTIN+${gtin}`
    });
  }

  // Handle FDA Recall Alert
  if (rule.isRecalled) {
    return NextResponse.json({
      status: "RECALLED_SAFETY_ALERT",
      warning: "⚠️ CRITICAL RECALL WARNING",
      gtin,
      lot,
      reason: rule.recallReason,
      fdaNoticeUrl: rule.targetUrl
    }, { status: 307 });
  }

  // Handle Lead Capture Integration
  if (rule.leadCaptureEnabled) {
    return NextResponse.json({
      status: "LEAD_CAPTURE_ACTIVE",
      gtin,
      lot,
      product: "Solid Hardwood 2-1/4 inch Oak",
      pricing: {
        installPerSqFt: 2.50,
        shoeMoldingPerLf: 0.25,
        sandStainRefinishPerSqFt: 1.80
      },
      message: "Scan from physical sample board detected. Instant turnaround quote available.",
      redirectUrl: rule.targetUrl
    });
  }

  // Default Redirection
  return NextResponse.redirect(rule.targetUrl, 302);
}
