"use client";

import React, { Suspense } from "react";
import Sidebar from "@/components/Sidebar";
import SowStudio from "@/components/SowStudio";
import { useSearchParams } from "next/navigation";

function SOWContent() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get("project_id") || undefined;

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[var(--background)] text-[var(--foreground)]">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <div className="max-w-6xl w-full mx-auto p-4 md:p-8 space-y-6">
          <SowStudio projectId={projectId} />
        </div>
      </main>
    </div>
  );
}

export default function SOWPage() {
  return (
    <Suspense fallback={<div className="flex h-screen items-center justify-center bg-[var(--background)] text-[var(--gold)] font-mono text-xs">Loading SOW Studio...</div>}>
      <SOWContent />
    </Suspense>
  );
}
