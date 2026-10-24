"use client";
import { useState } from "react";
import { DiscoveryFeed } from "@/components/discovery";
import { Filters } from "@/components/filters";
import { PageHeader } from "@/components/ui";
import type { SearchParams } from "@/lib/types";

const BASE: SearchParams = { types: ["model", "paper", "dataset"], sort: "published" };

export default function Research() {
  const [p, setP] = useState<SearchParams>(BASE);
  return (
    <>
      <PageHeader title="Research & Models" subtitle="Model releases, papers, benchmarks, API and pricing changes, deprecations. Benchmarks from a vendor's own announcement are vendor-reported unless an independent source confirms them; arXiv papers are preprints, not peer reviewed." />
      <Filters base={BASE} fields={["q", "type", "source", "verification", "published", "sort"]} onChange={setP} />
      <DiscoveryFeed params={p} grid={false} />
    </>
  );
}
