"use client";
import { useState } from "react";
import { DiscoveryFeed } from "@/components/discovery";
import { Filters } from "@/components/filters";
import { PageHeader } from "@/components/ui";
import type { SearchParams } from "@/lib/types";

const BASE: SearchParams = { types: ["tool", "agent", "repo"], sort: "score" };

export default function Tools() {
  const [p, setP] = useState<SearchParams>(BASE);
  return (
    <>
      <PageHeader title="AI Tools Directory" subtitle="Tools and projects you can use. Pricing is shown only when a source states it; open the item for capabilities, limitations, setup and evidence links. Mark items Saved or Tried to track your own testing." />
      <Filters base={BASE} fields={["q", "type", "category", "pricing", "openSource", "verification", "bookmark", "sort"]} onChange={setP} />
      <DiscoveryFeed params={p} />
    </>
  );
}
