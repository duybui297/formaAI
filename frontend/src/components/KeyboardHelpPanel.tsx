"use client";
import { Fragment } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface KeyboardHelpPanelProps {
  open: boolean;
  onClose: () => void;
}

const SHORTCUTS: Array<{ key: string; action: string }> = [
  { key: "j", action: "Next segment" },
  { key: "k", action: "Previous segment" },
  { key: "n", action: "Next flagged segment" },
  { key: "e", action: "Edit current segment" },
  { key: "r", action: "Regenerate current segment" },
  { key: "Esc", action: "Blur text field" },
  { key: "?", action: "Toggle this panel" },
];

export function KeyboardHelpPanel({ open, onClose }: KeyboardHelpPanelProps) {
  if (!open) return null;

  return (
    <div className="fixed right-4 top-[180px] z-50 w-72 bg-white border border-slate-200 rounded-lg shadow-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3
          className="text-sm font-semibold text-[#111111]"
          style={{ fontFamily: "var(--font-montserrat, sans-serif)" }}
        >
          Keyboard shortcuts
        </h3>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={onClose}
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
        {SHORTCUTS.map(({ key, action }) => (
          // CRITICAL: key must be on the Fragment (top-level element from .map),
          // NOT on the children. Named Fragment import required — <> shorthand
          // does not support the key prop.
          <Fragment key={key}>
            <kbd className="px-1.5 py-0.5 text-xs font-mono bg-slate-100 border border-slate-300 rounded justify-self-start">
              {key}
            </kbd>
            <span className="text-xs text-slate-600">{action}</span>
          </Fragment>
        ))}
      </div>
    </div>
  );
}
