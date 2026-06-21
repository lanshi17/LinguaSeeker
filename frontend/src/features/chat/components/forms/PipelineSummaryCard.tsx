import { useCallback, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils/cn";
import {
  CheckCircle2,
  FileText,
  Globe,
  MessageSquare,
  Search,
  Tag,
  Upload,
} from "lucide-react";

/** Slot schema mirrors the backend-emitted `action.slots` for
 *  `confirm-pipeline`. Keys are snake_case to avoid a mapping layer. */
export interface PipelineSummarySlots {
  source_type?: string;
  query?: string;
  identifiers?: string;
  gene_symbol?: string;
  disease_name?: string;
  variant_hgvs_p?: string;
  filename?: string;
}

interface PipelineSummaryCardProps {
  slots: PipelineSummarySlots;
  onConfirm: (slots: PipelineSummarySlots) => void;
  onModify?: () => void;
  isSubmitting?: boolean;
}

interface FieldRowProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  mono?: boolean;
}

function FieldRow({ icon, label, value, mono }: FieldRowProps) {
  return (
    <div className="flex items-start gap-2.5 py-1.5">
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center text-gray-400">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <span className="block text-[10px] font-semibold uppercase tracking-wider text-gray-400">
          {label}
        </span>
        <span
          className={cn(
            "block text-[13px] text-gray-900",
            mono && "font-mono",
          )}
        >
          {value}
        </span>
      </div>
    </div>
  );
}

/**
 * Renders the final "Ready to start?" summary produced by the chat agent's
 * conversational slot-gathering. The user either confirms (submitting the
 * pipeline) or modifies a slot by continuing the conversation.
 *
 * Replaces the deprecated PipelineConfirmCard that paired with the
 * now-removed inline form flow.
 */
export function PipelineSummaryCard({
  slots,
  onConfirm,
  onModify,
  isSubmitting,
}: PipelineSummaryCardProps) {
  const [submitted, setSubmitted] = useState(false);

  const handleConfirm = useCallback(() => {
    setSubmitted(true);
    onConfirm(slots);
  }, [onConfirm, slots]);

  const isOnline = slots.source_type !== "local";
  const sourceLabel = isOnline ? "Online Search" : "PDF Upload";
  const sourceIcon = isOnline ? (
    <Globe className="h-3.5 w-3.5" />
  ) : (
    <Upload className="h-3.5 w-3.5" />
  );

  const hasTarget =
    slots.gene_symbol || slots.disease_name || slots.variant_hgvs_p;

  const hasData = isOnline
    ? Boolean(slots.query || slots.identifiers)
    : true; // local upload flow: submission is valid once the user confirms

  return (
    <div className="w-full max-w-md overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-primary-600" aria-hidden />
          <span className="text-[13px] font-semibold text-gray-900">
            Ready to start pipeline
          </span>
        </div>
        <Badge variant="info">
          <span className="flex items-center gap-1">
            {sourceIcon}
            {sourceLabel}
          </span>
        </Badge>
      </div>

      <div className="divide-y divide-gray-50 px-4 py-2">
        {isOnline && slots.identifiers && (
          <FieldRow
            icon={<Tag className="h-3.5 w-3.5" />}
            label="Identifiers"
            value={slots.identifiers}
            mono
          />
        )}
        {isOnline && slots.query && (
          <FieldRow
            icon={<Search className="h-3.5 w-3.5" />}
            label="Search Query"
            value={slots.query}
          />
        )}
        {!isOnline && slots.filename && (
          <FieldRow
            icon={<FileText className="h-3.5 w-3.5" />}
            label="Document"
            value={slots.filename}
          />
        )}
        {!isOnline && !slots.filename && (
          <FieldRow
            icon={<Upload className="h-3.5 w-3.5" />}
            label="Document"
            value="Upload via /pipeline after confirmation"
          />
        )}
        {hasTarget && (
          <div className="py-1.5">
            <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-gray-400">
              Extraction Target
            </span>
            <div className="flex flex-wrap gap-1.5">
              {slots.gene_symbol && (
                <span className="rounded-full bg-cyan-50 px-2 py-0.5 font-mono text-[11px] font-medium text-cyan-700">
                  Gene: {slots.gene_symbol}
                </span>
              )}
              {slots.disease_name && (
                <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                  Disease: {slots.disease_name}
                </span>
              )}
              {slots.variant_hgvs_p && (
                <span className="rounded-full bg-violet-50 px-2 py-0.5 font-mono text-[11px] font-medium text-violet-700">
                  {slots.variant_hgvs_p}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 border-t border-gray-100 px-4 py-2.5">
        <Button
          size="sm"
          onClick={handleConfirm}
          disabled={!hasData || submitted}
          loading={isSubmitting || submitted}
          className="flex-1"
        >
          <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />
          Confirm & Start
        </Button>
        {onModify && (
          <button
            type="button"
            onClick={onModify}
            disabled={isSubmitting || submitted}
            className="flex items-center gap-1 rounded-md px-2.5 py-1.5 text-[12px] text-gray-500 transition-colors hover:bg-gray-50 hover:text-gray-700 disabled:opacity-50"
          >
            <MessageSquare className="h-3 w-3" />
            Modify via chat
          </button>
        )}
      </div>
    </div>
  );
}
