import { useI18n } from "@/lib/i18n";
import { Descriptions, Drawer, Empty, Tag, Typography } from "antd";
import type { GraphNode } from "../types/graphRag";

const { Text } = Typography;

/** Fill colors mirrored from KnowledgeGraphCanvas so the type tag matches the node. */
const TYPE_COLORS: Record<string, string> = {
  Gene: "#4763d0",
  Variant: "#4a9d5b",
  Disease: "#e0a326",
  Phenotype: "#d95555",
  Evidence: "#4aa3c4",
  EvidenceDoc: "#75839c",
  Document: "#3a9270",
  ProcessingRun: "#e08641",
};

const TYPE_LABELS: Record<string, string> = {
  EvidenceDoc: "Evidence",
};

interface EntityDetailDrawerProps {
  node: GraphNode | null;
  open: boolean;
  onClose: () => void;
}

/** Resolve a human-readable name across terminology and literature nodes. */
function resolveName(node: GraphNode): string {
  if (node.display_name) return node.display_name;
  for (const key of ["name", "doc_id"]) {
    const value = node.properties[key];
    if (value) return String(value);
  }
  return node.node_id;
}

/** Pick the entity type label from the node's labels. */
function resolveType(node: GraphNode): string {
  const key = node.labels.find((label) => label in TYPE_COLORS);
  return key ? (TYPE_LABELS[key] ?? key) : (node.labels[0] ?? "Unknown");
}

/**
 * Read-only detail panel for a clicked graph entity.
 *
 * Renders the node's type, name, id, and any extra properties returned by the
 * knowledge-graph API, so users can inspect a gene/variant/disease without
 * leaving the graph workspace.
 */
export function EntityDetailDrawer({ node, open, onClose }: EntityDetailDrawerProps) {
  const { t } = useI18n();

  const typeKey = node?.labels.find((label) => label in TYPE_COLORS);
  const tagColor = typeKey ? TYPE_COLORS[typeKey] : undefined;

  // Hide internal fields already shown above so the properties list stays clean.
  const hiddenKeys = new Set(["display_name", "name", "doc_id", "node_id"]);
  const properties = node
    ? Object.entries(node.properties).filter(
        ([key, value]) =>
          !hiddenKeys.has(key) && value !== null && value !== undefined && value !== "",
      )
    : [];

  return (
    <Drawer
      title={t("graphRag.detailTitle")}
      open={open}
      onClose={onClose}
      styles={{ body: { padding: "16px 24px" }, wrapper: { width: 420 } }}
    >
      {!node ? (
        <Empty description={t("graphRag.detailHint")} />
      ) : (
        <>
          <Descriptions
            column={1}
            size="small"
            labelStyle={{
              fontWeight: 500,
              color: "var(--color-text-secondary)",
              fontSize: 12,
              width: 96,
            }}
          >
            <Descriptions.Item label={t("graphRag.detailType")}>
              <Tag color={tagColor} style={{ margin: 0 }}>
                {resolveType(node)}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t("graphRag.detailName")}>
              <Text strong style={{ fontSize: 14 }}>
                {resolveName(node)}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label={t("graphRag.detailId")}>
              <Text copyable style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
                {node.node_id}
              </Text>
            </Descriptions.Item>
          </Descriptions>

          <Typography.Title level={5} style={{ marginTop: 20, marginBottom: 8 }}>
            {t("graphRag.detailProperties")}
          </Typography.Title>
          {properties.length === 0 ? (
            <Text type="secondary" style={{ fontSize: 13 }}>
              {t("graphRag.detailNoProperties")}
            </Text>
          ) : (
            <Descriptions
              column={1}
              size="small"
              bordered
              labelStyle={{
                fontWeight: 500,
                color: "var(--color-text-secondary)",
                fontSize: 12,
                width: 140,
              }}
            >
              {properties.map(([key, value]) => (
                <Descriptions.Item key={key} label={key}>
                  <Text style={{ fontSize: 13, wordBreak: "break-word" }}>
                    {typeof value === "object" ? JSON.stringify(value) : String(value)}
                  </Text>
                </Descriptions.Item>
              ))}
            </Descriptions>
          )}
        </>
      )}
    </Drawer>
  );
}
