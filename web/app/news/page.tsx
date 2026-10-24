"use client";
import { useState } from "react";
import { DiscoveryFeed } from "@/components/discovery";
import { Filters } from "@/components/filters";
import { PageHeader } from "@/components/ui";
import { daysAgo } from "@/lib/format";
import type { SearchParams } from "@/lib/types";

const BASE: SearchParams = { types: ["news", "discussion", "model"], sort: "published", publishedFrom: daysAgo(14) };

export default function News() {
  const [p, setP] = useState<SearchParams>(BASE);
  return (
    <>
      <PageHeader title="AI News" subtitle="Announcements, releases and discussions. Publication date and discovery time are shown separately — an old article we only just found is labelled as such." />
      <Filters base={BASE} fields={["q", "category", "source", "verification", "importance", "sort"]} onChange={setP} />
      <DiscoveryFeed params={p} grid={false} />
    </>
  );
}
