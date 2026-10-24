"use client";
import { useState } from "react";
import { DiscoveryFeed } from "@/components/discovery";
import { Filters } from "@/components/filters";
import { PageHeader } from "@/components/ui";
import type { SearchParams } from "@/lib/types";

const BASE: SearchParams = { category: "agents", sort: "discovered" };

export default function Agents() {
  const [p, setP] = useState<SearchParams>(BASE);
  return (
    <>
      <PageHeader title="AI Agents & Automation" subtitle="Agents, browser and computer-use tools, MCP servers, coding agents and workflow automation. Each item notes whether capabilities are demonstrated or only claimed — look for the claims note on the item page and treat “Experimental” as not production-ready." />
      <Filters base={BASE} fields={["q", "type", "openSource", "verification", "importance", "sort"]} onChange={setP} />
      <DiscoveryFeed params={p} />
    </>
  );
}
