/** Single literature candidate from provider search. */
export interface LiteratureCandidateItem {
  candidate_id: string;
  provider: string;
  route: "api" | "web";
  title: string;
  journal?: string;
  year?: number;
  language?: string;
  doi?: string;
  url?: string;
  identifiers?: Record<string, string>;
  detail_link?: string;
}

/** POST /tasks/requests/literature/candidates request. */
export interface LiteratureCandidateSearchRequest {
  target: string;
  disease?: string;
  country?: string;
  language?: string;
  source?: string;
  candidate_limit?: number;
  provider_hints?: string[];
}

/** POST /tasks/requests/literature/candidates response. */
export interface LiteratureCandidateSearchResponse {
  candidates: LiteratureCandidateItem[];
}
