import { useMutation } from "@tanstack/react-query";
import { queryGraphRag } from "../services/graphRag";
import type {
  GraphRagQueryRequest,
  GraphRagQueryResponse,
} from "../types/graphRag";

export function useGraphRagQuery() {
  return useMutation<GraphRagQueryResponse, Error, GraphRagQueryRequest>({
    mutationFn: queryGraphRag,
  });
}
