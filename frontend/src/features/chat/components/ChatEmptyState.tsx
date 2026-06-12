"use client";

import { useEffect, useState } from "react";

import type { PromptItem } from "./prompts";
import "./ChatEmptyState.css";

export interface ChatEmptyStateProps {
  prompts: readonly PromptItem[];
  onPromptSelect: (key: string) => void;
  sessionCount: number;
}

function formatLabTime(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())} · UTC+8`;
}

export function ChatEmptyState({
  prompts,
  onPromptSelect,
  sessionCount,
}: ChatEmptyStateProps) {
  const [labTime, setLabTime] = useState<string>(() => formatLabTime(new Date()));

  // Hold the count at 0 for the first client render so the markup matches
  // the SSR pass. The real count arrives on the next tick and then
  // matches the parent's authoritative state.
  const [hydratedCount, setHydratedCount] = useState(0);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot hydration gate; updating once after mount is the standard Next.js SSR/CSR pattern and cannot cascade because the dep is a primitive number.
    setHydratedCount(sessionCount);
  }, [sessionCount]);

  useEffect(() => {
    const id = setInterval(() => setLabTime(formatLabTime(new Date())), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="ce-empty">
      <div aria-hidden="true" className="ce-empty__grid" />

      <div className="ce-empty__inner">
        <header className="ce-empty__masthead">
          <div className="ce-empty__rule ce-empty__rule--double" aria-hidden="true" />

          <p className="ce-empty__kicker">
            <span className="ce-empty__pulse" aria-hidden="true" />
            <span>Cross Evidence Agent · v2.4.0</span>
            <span className="ce-empty__dot" aria-hidden="true">·</span>
            <span>{hydratedCount} session{hydratedCount === 1 ? "" : "s"} on record</span>
            <span className="ce-empty__dot" aria-hidden="true">·</span>
            <span className="ce-empty__time">{labTime}</span>
          </p>

          <h1 className="ce-empty__title">
            <span className="ce-empty__title-row">
              <span className="ce-empty__title-num" aria-hidden="true">§01</span>
              <span className="ce-empty__title-text">
                A <em>literature</em> instrument for
                <br />
                <em>variant</em> &amp; <em>evidence</em> classification.
              </span>
            </span>
          </h1>

          <p className="ce-empty__lede">
            Not a general-purpose chatbot. Cross Evidence ingests biomedical
            literature, runs a four-phase extraction pipeline (acquisition →
            cross-lingual dual extraction → entity standardisation →
            expert-in-the-loop review), and grounds every claim in source
            coordinates. Ask it to <em>classify</em>, <em>extract</em>,
            <em> search</em>, or <em>interpret</em>.
          </p>

          <div className="ce-empty__rule" aria-hidden="true" />
        </header>

        <section className="ce-empty__section" aria-labelledby="specimens">
          <div className="ce-empty__section-head">
            <h2 id="specimens" className="ce-empty__section-title">
              <span className="ce-empty__section-num">01.</span>
              Specimens of capability
            </h2>
            <p className="ce-empty__section-hint">
              Select a specimen — the agent will respond in place.
            </p>
          </div>

          <ul className="ce-empty__grid-cards">
            {prompts.map((prompt, index) => (
              <li
                key={prompt.key}
                className="ce-empty__card stagger-in"
                style={{ animationDelay: `${120 + index * 70}ms` }}
              >
                <button
                  type="button"
                  className="ce-empty__card-btn"
                  onClick={() => onPromptSelect(prompt.key)}
                >
                  <span className="ce-empty__card-corner" aria-hidden="true">
                    {String(index + 1).padStart(2, "0")}
                  </span>

                  <span className="ce-empty__card-eyebrow">
                    {prompt.eyebrow}
                  </span>

                  <span className="ce-empty__card-label">
                    {prompt.label}
                  </span>

                  <span className="ce-empty__card-desc">
                    {prompt.description}
                  </span>

                  <span className="ce-empty__card-example">
                    <span className="ce-empty__card-example-label">
                      e.g.
                    </span>
                    <span className="ce-empty__card-example-text">
                      {prompt.example}
                    </span>
                  </span>

                  <span className="ce-empty__card-arrow" aria-hidden="true">
                    →
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>

        <footer className="ce-empty__footer">
          <div className="ce-empty__rule" aria-hidden="true" />
          <div className="ce-empty__footer-row">
            <p className="ce-empty__footnote">
              <span className="ce-empty__footnote-key">Note.</span>
              {" "}The agent does not provide clinical diagnoses. Outputs
              are research-grade evidence for review by qualified
              professionals.
            </p>
            <p className="ce-empty__sig">
              <span className="ce-empty__sig-line" aria-hidden="true" />
              <span>
                Model: reasoning LLM · SSE stream · grounded citations
              </span>
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
}
