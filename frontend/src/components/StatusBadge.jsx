import React from "react";

const STYLES = {
  active: { color: "#34D399", bg: "rgba(52,211,153,0.08)", border: "rgba(52,211,153,0.3)" },
  off: { color: "#FB7185", bg: "rgba(251,113,133,0.08)", border: "rgba(251,113,133,0.3)" },
  new: { color: "#FBBF24", bg: "rgba(251,191,36,0.08)", border: "rgba(251,191,36,0.3)" },
  archive: { color: "#A3A3A3", bg: "rgba(163,163,163,0.08)", border: "rgba(163,163,163,0.3)" },
};

export default function StatusBadge({ status }) {
  const s = STYLES[status] || STYLES.archive;
  return (
    <span
      data-testid={`status-${status}`}
      className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider border"
      style={{ color: s.color, background: s.bg, borderColor: s.border }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ background: s.color, boxShadow: `0 0 8px ${s.color}` }}
      />
      {status}
    </span>
  );
}
