"use client";
import { useState } from "react";
import { DiscoveryFeed } from "@/components/discovery";
import { Filters } from "@/components/filters";
import { PageHeader } from "@/components/ui";
import type { SearchParams } from "@/lib/types";

const BASE: SearchParams = { hiddenGems: true, sort: "score" };

export default function Gems() {
  return <GemsInner />;
}
function GemsInner() {
  const [p, setP] = useState<SearchParams>(BASE);
  return (
    <>
      <PageHeader title="Hidden Gems" subtitle="Lesser-known tools and young projects that look useful. These are early and often unproven — check maintenance signals and limitations before relying on one." />
      <Filters base={BASE} fields={["q", "type", "category", "openSource", "sort"]} onChange={setP} />
      <DiscoveryFeed params={p} empty="No hidden gems flagged yet. Candidates come from rising GitHub repos and Hugging Face projects with modest popularity." />
    </>
  );
}
