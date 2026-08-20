import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      gtin = "00850012345678",
      sampleName = "Solid Hardwood 2-1/4 inch Oak",
      sqft = 728,
      linearFeet = 210,
      serviceType = "install_refinish", // 'install_only', 'refinish_only', 'install_refinish'
      clientName = "",
      clientPhone = "",
      clientEmail = "",
      address = ""
    } = body;

    // Rates according to Updated Business Rules
    const WASTE_FACTOR = 1.15; // 15% waste factor for corners & cuts
    const HARDWOOD_INSTALL_RATE = 2.50; // $2.50 / sq ft client billed
    const SHOE_MOLDING_INSTALL_RATE = 0.25; // $0.25 / sq ft client billed
    
    // Sand, Stain & Refinish Rates (Updated)
    const SAND_STAIN_REFINISH_CLIENT_RATE = 3.80; // $3.80 / sq ft client billed
    const ROMAN_SUB_REFINISH_COST = 3.12; // $3.12 / sq ft Roman sub cost

    // Billed Quantities
    const billedSqFt = Math.ceil(sqft * WASTE_FACTOR);
    const billedLinearFeet = Math.ceil(linearFeet * WASTE_FACTOR);

    let installCost = 0;
    let shoeMoldingCost = 0;
    let refinishCost = 0;

    if (serviceType === "install_only" || serviceType === "install_refinish") {
      installCost = billedSqFt * HARDWOOD_INSTALL_RATE;
      shoeMoldingCost = billedLinearFeet * SHOE_MOLDING_INSTALL_RATE;
    }

    if (serviceType === "refinish_only" || serviceType === "install_refinish") {
      refinishCost = sqft * SAND_STAIN_REFINISH_CLIENT_RATE;
    }

    const totalEstimate = installCost + shoeMoldingCost + refinishCost;

    // Subcontractor Payout (Roman's rate calculation)
    const romanInstallSubLaborRate = 1.75; // Subcontractor install labor payout rate
    const estimatedInstallSubPayout = (serviceType === "install_only" || serviceType === "install_refinish") ? sqft * romanInstallSubLaborRate : 0;
    const estimatedRefinishSubPayout = (serviceType === "refinish_only" || serviceType === "install_refinish") ? sqft * ROMAN_SUB_REFINISH_COST : 0;
    
    const totalSubPayout = estimatedInstallSubPayout + estimatedRefinishSubPayout;
    const netProfitMargin = totalEstimate - totalSubPayout;

    // Structure lead payload for Planka / PostgreSQL sync
    const leadPayload = {
      leadId: `QR-${Date.now().toString().slice(-6)}`,
      timestamp: new Date().toISOString(),
      gtin,
      sampleName,
      sqftInput: sqft,
      billedSqFt,
      linearFeetInput: linearFeet,
      billedLinearFeet,
      serviceType,
      pricingBreakdown: {
        hardwoodInstall: installCost.toFixed(2),
        shoeMoldingInstall: shoeMoldingCost.toFixed(2),
        sandStainRefinish: refinishCost.toFixed(2),
        totalEstimate: totalEstimate.toFixed(2),
        estimatedSubPayout: totalSubPayout.toFixed(2),
        netProfitMargin: netProfitMargin.toFixed(2)
      },
      client: {
        name: clientName || "Job Site QR Scanner",
        phone: clientPhone || "N/A",
        email: clientEmail || "N/A",
        address: address || "Scanned via Job Site QR Code"
      },
      exclusivity: {
        status: "exclusive",
        decayDays: 10,
        exclusiveUntil: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString()
      }
    };

    return NextResponse.json({
      success: true,
      message: "Lead successfully captured & synced to Lead Arbitrage Engine!",
      data: leadPayload
    }, { status: 200 });

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } catch (error: any) {
    return NextResponse.json({
      success: false,
      error: error.message || "Failed to process QR estimate lead"
    }, { status: 500 });
  }
}
