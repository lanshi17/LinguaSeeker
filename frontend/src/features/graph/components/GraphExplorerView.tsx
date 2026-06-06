"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { GraphSearchForm } from "./GraphSearchForm";
import { GraphNodeList } from "./GraphNodeList";
import { GraphEdgeView } from "./GraphEdgeView";
import { GraphStatsPanel } from "./GraphStatsPanel";
import { DocumentResyncForm } from "./DocumentResyncForm";
import { useGraphSearch } from "../hooks/useGraphSearch";
import { useToastStore } from "@/stores/toastStore";
import type { GraphSearchRequest } from "../types/graph";

/** Client wrapper for the knowledge graph explorer. */
export function GraphExplorerView() {
  const {
    search,
    searchResults,
    isSearching,
    fetchStats,
    stats,
    isLoadingStats,
    resyncDocument,
    isResyncing,
  } = useGraphSearch();

  const addToast = useToastStore((s) => s.addToast);
  const [hasSearched, setHasSearched] = useState(false);

  async function handleSearch(params: GraphSearchRequest) {
    setHasSearched(true);
    try {
      await search(params);
    } catch {
      addToast({ level: "error", title: "Graph search failed" });
    }
  }

  async function handleResync(docId: string) {
    try {
      await resyncDocument(docId);
      addToast({ level: "success", title: "Document resynced" });
    } catch {
      addToast({ level: "error", title: "Resync failed" });
    }
  }

  return (
    <div className="space-y-6">
      <ErrorBoundary>
        <Card>
          <GraphSearchForm onSearch={handleSearch} isSearching={isSearching} />
        </Card>
      </ErrorBoundary>

      {hasSearched && searchResults && (
        <div className="grid gap-6 lg:grid-cols-2">
          <ErrorBoundary>
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-gray-700">
                Nodes ({searchResults.nodes.length})
              </h3>
              <GraphNodeList nodes={searchResults.nodes} />
            </Card>
          </ErrorBoundary>

          <ErrorBoundary>
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-gray-700">
                Edges ({searchResults.edges.length})
              </h3>
              <GraphEdgeView edges={searchResults.edges} />
            </Card>
          </ErrorBoundary>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <ErrorBoundary>
          <GraphStatsPanel
            stats={stats}
            onLoad={() => fetchStats()}
            isLoading={isLoadingStats}
          />
        </ErrorBoundary>

        <ErrorBoundary>
          <Card>
            <h3 className="mb-3 text-sm font-semibold text-gray-700">
              Resync Document
            </h3>
            <DocumentResyncForm
              onResync={handleResync}
              isResyncing={isResyncing}
            />
          </Card>
        </ErrorBoundary>
      </div>
    </div>
  );
}
