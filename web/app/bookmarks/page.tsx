"use client";
import { useState } from "react";
import { DiscoveryFeed } from "@/components/discovery";
import { Filters } from "@/components/filters";
import { PageHeader } from "@/components/ui";
import type { SearchParams } from "@/lib/types";

const TABS = [["any", "All saved"], ["saved", "Saved"], ["tried", "Tried"], ["not_useful", "Not useful"]] as const;

export default function Bookmarks() {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("any");
  const [p, setP] = useState<SearchParams>({});
  return (
    <>
      <PageHeader title="Bookmarks" subtitle="Your saved items, testing status and notes. Only you can see these — they are protected by row-level security." />
      <div className="mb-4 flex flex-wrap gap-2" role="tablist">
        {TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={`chip ${tab === k ? "chip-on" : ""}`} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      <Filters base={{}} fields={["q", "type", "category", "sort"]} onChange={setP} />
      <DiscoveryFeed params={{ ...p, bookmark: tab }} empty="Nothing here yet. Use ☆ Save or ✓ Tried on any item." />
    </>
  );
}
