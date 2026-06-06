/** A single text span with optional highlight annotations. */
export interface TextSpan {
  text: string;
  start_offset: number;
  end_offset: number;
  label?: string;
}

/** GET /source-link/{id}/{track} response. */
export interface TrackSpan {
  track: "original" | "translated";
  spans: TextSpan[];
  language?: string;
}

/** GET /source-link/{id}/bilingual response. */
export interface BilingualSpan {
  original: TrackSpan;
  translated: TrackSpan;
}

/** Dictionary of track spans keyed by track name. */
export interface SourceSpanDict {
  original?: TrackSpan;
  translated?: TrackSpan;
}
