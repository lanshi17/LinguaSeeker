import type { RefObject } from "react";
import { Select, Tooltip } from "antd";
import { ANNOTATION_COLORS } from "../../types/annotations";
import { CATEGORY_COLORS } from "../../utils/evidenceDocument";
import type { FieldTypeOption } from "../../utils/fieldAssignment";
import type { SelectionInfo } from "./contracts";
import { useI18n } from "@/lib/i18n";

interface AnnotationSelectionToolbarProps {
  selection: SelectionInfo;
  popupRef: RefObject<HTMLDivElement>;
  canCreate: boolean;
  canAssignField: boolean;
  creatingColor: string | null;
  assigningField: boolean;
  fieldTypes: FieldTypeOption[];
  onCreate: (color: string) => void;
  onAssignField: (fieldType: string) => void;
}

export function AnnotationSelectionToolbar({
  selection,
  popupRef,
  canCreate,
  canAssignField,
  creatingColor,
  assigningField,
  fieldTypes,
  onCreate,
  onAssignField,
}: AnnotationSelectionToolbarProps) {
  const { t } = useI18n();
  const toolbarWidthOffset = canCreate && canAssignField ? 140 : 90;

  return (
    <div
      ref={popupRef}
      onMouseDown={(event) => event.stopPropagation()}
      style={{
        position: "fixed",
        top: Math.max(8, selection.rect.top - 48),
        left: Math.max(8, selection.rect.left + selection.rect.width / 2 - toolbarWidthOffset),
        zIndex: 1050,
        display: "flex",
        gap: 6,
        alignItems: "center",
        padding: "6px 8px",
        background: "var(--color-surface)",
        borderRadius: 8,
        boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
      }}
    >
      {canCreate && ANNOTATION_COLORS.map((color) => (
        <Tooltip key={color} title={t("annotation.create")}>
          <button
            type="button"
            onClick={() => onCreate(color)}
            disabled={creatingColor !== null}
            style={{
              width: 22,
              height: 22,
              borderRadius: "50%",
              border: "2px solid var(--color-surface)",
              boxShadow: "0 0 0 1px var(--color-text-muted)",
              backgroundColor: color,
              cursor: creatingColor === null ? "pointer" : "wait",
              opacity: creatingColor && creatingColor !== color ? 0.45 : 1,
              padding: 0,
            }}
            aria-label={t("annotation.createWithColor", { color })}
          />
        </Tooltip>
      ))}
      {canCreate && canAssignField && (
        <div style={{ width: 1, height: 20, background: "var(--color-border)", margin: "0 2px" }} />
      )}
      {canAssignField && fieldTypes.length > 0 && (
        <Select
          showSearch
          placeholder={t("annotation.addField")}
          size="small"
          style={{ width: 160, fontSize: 11 }}
          disabled={assigningField}
          loading={assigningField}
          popupMatchSelectWidth={260}
          optionFilterProp="label"
          onChange={(fieldType: string) => onAssignField(fieldType)}
          options={fieldTypes.map((fieldType) => {
            const hex = fieldType.category && CATEGORY_COLORS[fieldType.category]?.hex;
            return {
              value: fieldType.fieldId,
              label: (
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  {hex && (
                    <span style={{ width: 8, height: 8, borderRadius: "50%", backgroundColor: hex, flexShrink: 0 }} />
                  )}
                  <span style={{ fontWeight: 500 }}>{fieldType.label}</span>
                  <span style={{ fontSize: 10, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                    {fieldType.fieldId}
                  </span>
                </span>
              ),
            };
          })}
          filterOption={(input, option) => {
            const fieldType = fieldTypes.find((item) => item.fieldId === option?.value);
            if (!fieldType) return false;
            const search = `${fieldType.label} ${fieldType.fieldId} ${fieldType.category ?? ""}`.toLowerCase();
            return search.includes(input.toLowerCase());
          }}
        />
      )}
    </div>
  );
}
