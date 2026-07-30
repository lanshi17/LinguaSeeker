import { KnowledgeGraphCanvas, type KnowledgeGraph } from "@/features/graphrag";
import { useI18n } from "@/lib/i18n";
import { ApartmentOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Spin, Typography } from "antd";
import { useNavigate } from "react-router-dom";

const { Paragraph, Text } = Typography;

export interface ChatGraphResultCardProps {
  question: string;
  status: "loading" | "done" | "error";
  answer?: string;
  subgraph?: KnowledgeGraph;
  error?: string;
}

/**
 * Renders an inline knowledge-graph Q&A result inside the chat stream.
 *
 * The grounded answer and subgraph come from the GraphRAG engine (not the
 * chat router LLM). A "view in graph" action deep-links into the dedicated
 * exploration workspace, seeded with any Gene node from the subgraph.
 */
export function ChatGraphResultCard({
  status,
  answer,
  subgraph,
  error,
}: ChatGraphResultCardProps) {
  const { t } = useI18n();
  const navigate = useNavigate();

  if (status === "loading") {
    return (
      <Card variant="borderless" style={{ background: "var(--color-bg-muted)" }}>
        <Spin />
        <Text type="secondary" style={{ marginLeft: 12 }}>
          {t("chat.graph.loading")}
        </Text>
      </Card>
    );
  }

  if (status === "error") {
    return (
      <Alert
        type="error"
        showIcon
        message={t("chat.graph.error")}
        description={error}
      />
    );
  }

  const nodes = subgraph?.nodes ?? [];
  const edges = subgraph?.edges ?? [];
  const hasGraph = nodes.length > 0;

  // Seed the explorer deep-link from the first Gene node, falling back to
  // Disease / Variant so "view in graph" always lands on a meaningful seed.
  const seedParam = (() => {
    const gene = nodes.find((n) => n.labels.includes("Gene"));
    if (gene) return `gene=${encodeURIComponent(gene.display_name)}`;
    const disease = nodes.find((n) => n.labels.includes("Disease"));
    if (disease) return `disease=${encodeURIComponent(disease.display_name)}`;
    const variant = nodes.find((n) => n.labels.includes("Variant"));
    if (variant) return `variant=${encodeURIComponent(variant.display_name)}`;
    return "";
  })();

  return (
    <Card
      title={t("chat.graph.title")}
      variant="borderless"
      style={{ background: "var(--color-bg-muted)" }}
      extra={
        hasGraph ? (
          <Button
            type="link"
            size="small"
            icon={<ApartmentOutlined />}
            onClick={() =>
              navigate(seedParam ? `/graphrag?${seedParam}` : "/graphrag")
            }
          >
            {t("chat.graph.viewInGraph")}
          </Button>
        ) : null
      }
    >
      {answer && (
        <Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: hasGraph ? 16 : 0 }}>
          {answer}
        </Paragraph>
      )}
      {hasGraph && (
        <>
          <KnowledgeGraphCanvas graph={{ nodes, edges }} height={420} />
          <Text type="secondary" style={{ display: "block", marginTop: 8 }}>
            {t("graphRag.exploreCounts", {
              nodes: nodes.length,
              edges: edges.length,
            })}
          </Text>
        </>
      )}
    </Card>
  );
}
