import { EntityGraphExplorer } from "./EntityGraphExplorer";

/**
 * GraphRAG entry view — entity-driven knowledge graph explorer.
 *
 * This is the dedicated visual workspace for the gene-disease-variant triple.
 * Natural-language Q&A now lives in the Chat feature, where the chat router
 * dispatches graph-qa actions and the grounded answer + subgraph is rendered
 * inline. A "View in graph" deep-link from chat navigates here with URL
 * params (e.g. /graphrag?gene=COL2A1).
 */
export function GraphRagView() {
  return <EntityGraphExplorer />;
}
