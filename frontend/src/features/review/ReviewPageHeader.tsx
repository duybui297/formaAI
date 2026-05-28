"use client";
import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { authFetch } from "@/lib/auth";
import type { JobSummary } from "@/lib/types";

interface ReviewPageHeaderProps {
  job: JobSummary & { glossary_name?: string | null };
}

export function ReviewPageHeader({ job }: ReviewPageHeaderProps) {
  const [exporting, setExporting] = useState(false);
  const { toast } = useToast();

  const canExport = job.status === "done" || job.status === "needs_review";

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await authFetch(`/jobs/${job.id}/export`, {
        method: "POST",
      });
      if (!res.ok) {
        let detail = "Could not export document. Try again.";
        try {
          const body = await res.json();
          if (body?.detail) {
            detail = body.detail;
          }
        } catch {
          // response was not JSON — keep generic message
        }
        toast({ title: detail, variant: "destructive" });
        return;
      }
      // Trigger browser download — preserve original extension so PPTX / PDF
      // jobs get the correct filename (was hardcoded ".docx" before Phase 3).
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const extMatch = job.original_filename.match(/\.[^./\\]+$/);
      const ext = extMatch ? extMatch[0] : ".docx";
      a.download = job.original_filename.replace(/(\.\w+)?$/, `_translated${ext}`);
      a.click();
      // Defer revocation so Safari/Firefox finish reading the blob before it is released.
      setTimeout(() => URL.revokeObjectURL(url), 100);
      toast({ title: "Export ready — downloading." });
    } catch {
      toast({
        title: "Network error — export could not be initiated. Try again.",
        variant: "destructive",
      });
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="sticky top-14 z-10 flex items-center gap-4 h-16 px-8 bg-white border-b border-slate-200">
      <Link
        href="/translator"
        className="text-sm text-slate-500 hover:text-slate-700 shrink-0"
      >
        ← All Jobs
      </Link>

      <div className="flex-1 min-w-0">
        <h1
          className="text-xl font-semibold truncate text-[#111111]"
          style={{ fontFamily: "var(--font-montserrat, sans-serif)" }}
        >
          {job.original_filename}
        </h1>
        <p className="text-xs text-slate-400">
          {job.source_lang} → {job.target_lang}
          {job.glossary_name && (
            <span className="ml-2 px-1.5 py-0.5 bg-violet-50 text-violet-700 rounded text-xs">
              Glossary: {job.glossary_name}
            </span>
          )}
        </p>
      </div>

      {canExport && (
        <Button
          disabled={exporting}
          onClick={handleExport}
          className="shrink-0 bg-violet-500 hover:bg-violet-600 text-white"
        >
          {exporting ? "Exporting…" : "Export Document"}
        </Button>
      )}
    </div>
  );
}
