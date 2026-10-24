"use client";
import { useState } from "react";
import { DiscoveryFeed } from "@/components/discovery";
import { Filters } from "@/components/filters";
import { PageHeader } from "@/components/ui";
import type { SearchParams } from "@/lib/types";

const BASE: SearchParams = { sort: "published" };

export default function Search() {
  const [p, setP] = useState<SearchParams>(BASE);
  return (
    <>
      <PageHeader title="Search & Archive" subtitle="Full-text search over every stored discovery and summary. Results are filtered and paginated in the database." />
      <Filters base={BASE} onChange={setP}
        fields={["q", "type", "category", "source", "pricing", "openSource", "verification", "importance", "bookmark", "sort", "published", "discovered"]} />
      <DiscoveryFeed params={p} grid={false} pageSize={25} empty="No matches. Try fewer filters or different words." />
    </>
  );
}
