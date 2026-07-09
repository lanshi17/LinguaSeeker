import { useEffect, useState } from "react";
import { DeleteOutlined } from "@ant-design/icons";
import { Button, Input } from "antd";
import { useI18n } from "@/lib/i18n";
import {
  ANNOTATION_COLORS,
  DEFAULT_ANNOTATION_COLOR,
  type UserAnnotation,
} from "../../types/annotations";
import type { AnnotationOperation, AnnotationUpdatePayload } from "./contracts";

interface AnnotationEditorProps {
  annotation: UserAnnotation;
  onUpdate?: (id: string, payload: AnnotationUpdatePayload) => AnnotationOperation;
  onDelete?: (id: string) => AnnotationOperation;
  onDone: () => void;
}

export function AnnotationEditor({
  annotation,
  onUpdate,
  onDelete,
  onDone,
}: AnnotationEditorProps) {
  const { t } = useI18n();
  const [note, setNote] = useState(annotation.note ?? "");
  const [color, setColor] = useState(annotation.color ?? DEFAULT_ANNOTATION_COLOR);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    setNote(annotation.note ?? "");
    setColor(annotation.color ?? DEFAULT_ANNOTATION_COLOR);
  }, [annotation.id, annotation.color, annotation.note]);

  const handleSave = () => {
    if (!onUpdate || saving || deleting) return;
    setSaving(true);
    Promise.resolve(onUpdate(annotation.id, { color, note: note.trim() || null }))
      .then(onDone)
      .catch(() => undefined)
      .finally(() => setSaving(false));
  };

  const handleDelete = () => {
    if (!onDelete || saving || deleting) return;
    setDeleting(true);
    Promise.resolve(onDelete(annotation.id))
      .then(onDone)
      .catch(() => undefined)
      .finally(() => setDeleting(false));
  };

  return (
    <div style={{ width: 260, display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {ANNOTATION_COLORS.map((candidate) => (
          <button
            key={candidate}
            type="button"
            onClick={() => setColor(candidate)}
            style={{
              width: 22,
              height: 22,
              borderRadius: "50%",
              border: color === candidate ? "2px solid var(--color-text)" : "2px solid var(--color-surface)",
              boxShadow: "0 0 0 1px var(--color-text-muted)",
              backgroundColor: candidate,
              cursor: "pointer",
              padding: 0,
            }}
            aria-label={t("annotation.pickColor", { color: candidate })}
          />
        ))}
      </div>
      <Input.TextArea
        value={note}
        onChange={(event) => setNote(event.target.value)}
        placeholder={t("annotation.notePlaceholder")}
        autoSize={{ minRows: 2, maxRows: 5 }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
        <Button
          danger
          size="small"
          icon={<DeleteOutlined />}
          onClick={handleDelete}
          loading={deleting}
          disabled={!onDelete || saving}
        >
          {t("common.delete")}
        </Button>
        <Button
          type="primary"
          size="small"
          onClick={handleSave}
          loading={saving}
          disabled={!onUpdate || deleting}
        >
          {t("common.save")}
        </Button>
      </div>
    </div>
  );
}
