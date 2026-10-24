"use client";
import { useState } from "react";
import { DiscoveryFeed } from "@/components/discovery";
import { Filters } from "@/components/filters";
import { PageHeader } from "@/components/ui";
import { daysAgo } from "@/lib/format";
import type { SearchParams } from "@/lib/types";

const BASE: SearchParams = { types: ["repo"], sort: "published", publishedFrom: daysAgo(30) };

export default function GitHub() {
  const [p, setP] = useState<SearchParams>(BASE);
  return (
    <>
      <PageHeader title="GitHub & Open Source" subtitle="Releases from a watchlist of projects plus rising new repositories. Star counts measure popularity, not reliability or security — open an item to see licence, last push, open issues and security notes." />
      <Filters base={BASE} fields={["q", "category", "source", "openSource", "importance", "sort"]} onChange={setP} />
      <DiscoveryFeed params={p} />
    </>
  );
}
