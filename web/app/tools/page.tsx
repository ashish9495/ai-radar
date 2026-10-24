"use client";
import { useState } from "react";
import { DiscoveryFeed } from "@/components/discovery";
import { Filters } from "@/components/filters";
import { PageHeader } from "@/components/ui";
import { daysAgo } from "@/lib/format";
import type { SearchParams } from "@/lib/types";

const BASE: SearchParams = { types: ["tool", "agent"], sort: "published", publishedFrom: daysAgo(7) };

export default function Tools() {
  const [p, setP] = useState<SearchParams>(BASE);
  return (
    <>
      <PageHeader title="AI Tools Directory" subtitle="Newly launched AI tools, newest first — from Product Hunt's AI category and Hacker News “Show HN” (checked every 15 minutes), plus releases and news. Each card links to the tool's own site and the discussion where it launched. Launch claims are the makers' own; mark tools Tried once you've tested them." />
      <Filters base={BASE} fields={["q", "type", "category", "pricing", "openSource", "verification", "bookmark", "sort"]} onChange={setP} />
      <DiscoveryFeed params={p} />
    </>
  );
}
