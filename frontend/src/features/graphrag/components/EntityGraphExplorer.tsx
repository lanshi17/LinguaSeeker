import { useI18n } from "@/lib/i18n";
import { SearchOutlined } from "@ant-design/icons";
import { Button, Card, Col, Empty, Form, Input, Row, Spin, Typography } from "antd";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useKnowledgeGraph } from "../hooks/useKnowledgeGraph";
import { KnowledgeGraphCanvas } from "./KnowledgeGraphCanvas";
import { EntityDetailDrawer } from "./EntityDetailDrawer";
import type { GraphNode } from "../types/graphRag";

const { Title, Text, Paragraph } = Typography;

/**
 * Gene used to seed the default example graph when the page opens without any
 * search input or deep-link params. It carries the full gene-disease-variant
 * triple in the graph (terminology baseline plus literature evidence), so the
 * default view demonstrates the triple relation instead of opening empty.
 */
const EXAMPLE_GENE = "EGFR";

interface ExplorerFormValues {
  gene?: string;
  disease?: string;
  variant?: string;
  phenotype?: string;
}

interface ExplorerQuery {
  geneSymbol?: string;
  diseaseName?: string;
  variantHgvsP?: string;
  phenotype?: string;
}

/**
 * Entity-driven explorer for the gene-disease-variant triple.
 *
 * Queries the knowledge graph directly by entity and renders the resulting
 * subgraph, where each gene-disease-variant relation is bridged by the
 * evidence documents that support it. On first load (no deep-link params) it
 * shows an example graph so the workspace is never empty.
 */
export function EntityGraphExplorer() {
  const { t } = useI18n();
  const [form] = Form.useForm<ExplorerFormValues>();
  const [searchParams] = useSearchParams();
  const urlQuery = {
    geneSymbol: searchParams.get("gene") ?? undefined,
    diseaseName: searchParams.get("disease") ?? undefined,
    variantHgvsP: searchParams.get("variant") ?? undefined,
    phenotype: searchParams.get("phenotype") ?? undefined,
  };
  const hasUrlQuery = Boolean(
    urlQuery.geneSymbol ||
      urlQuery.diseaseName ||
      urlQuery.variantHgvsP ||
      urlQuery.phenotype,
  );
  const [query, setQuery] = useState<ExplorerQuery>(() =>
    hasUrlQuery ? urlQuery : { geneSymbol: EXAMPLE_GENE },
  );
  const [isExample, setIsExample] = useState(!hasUrlQuery);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // Seed the form + query from URL params so chat's "view in graph" deep-link
  // (e.g. /graphrag?gene=COL2A1) opens directly on the requested entity. This
  // overrides the default example graph.
  useEffect(() => {
    const gene = searchParams.get("gene") ?? undefined;
    const disease = searchParams.get("disease") ?? undefined;
    const variant = searchParams.get("variant") ?? undefined;
    const phenotype = searchParams.get("phenotype") ?? undefined;
    if (!gene && !disease && !variant && !phenotype) return;
    setIsExample(false);
    form.setFieldsValue({ gene, disease, variant, phenotype });
    setQuery({
      geneSymbol: gene,
      diseaseName: disease,
      variantHgvsP: variant,
      phenotype,
    });
  }, [searchParams, form]);

  const hasQuery = Boolean(
    query.geneSymbol || query.diseaseName || query.variantHgvsP || query.phenotype,
  );

  const { data, isFetching, isPending, error } = useKnowledgeGraph({
    ...query,
    mode: "full",
    enabled: hasQuery,
  });

  const handleSubmit = (values: ExplorerFormValues) => {
    setIsExample(false);
    setSelectedNode(null);
    setQuery({
      geneSymbol: values.gene?.trim() || undefined,
      diseaseName: values.disease?.trim() || undefined,
      variantHgvsP: values.variant?.trim() || undefined,
      phenotype: values.phenotype?.trim() || undefined,
    });
  };

  const nodeCount = data?.nodes.length ?? 0;
  const edgeCount = data?.edges.length ?? 0;
  const hasGraph = nodeCount > 0;

  const graphNodes = data?.nodes;
  const handleNodeClick = useCallback(
    (nodeId: string) => {
      setSelectedNode(graphNodes?.find((n) => n.node_id === nodeId) ?? null);
    },
    [graphNodes],
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <Card>
        <Title level={4}>{t("graphRag.exploreTitle")}</Title>
        <Paragraph type="secondary">{t("graphRag.exploreDescription")}</Paragraph>
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Row gutter={16}>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="gene" label={t("graphRag.geneLabel")}>
                <Input placeholder={t("graphRag.genePlaceholder")} allowClear />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="disease" label={t("graphRag.diseaseLabel")}>
                <Input placeholder={t("graphRag.diseasePlaceholder")} allowClear />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="variant" label={t("graphRag.variantLabel")}>
                <Input placeholder={t("graphRag.variantPlaceholder")} allowClear />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="phenotype" label={t("graphRag.phenotypeLabel")}>
                <Input placeholder={t("graphRag.phenotypePlaceholder")} allowClear />
              </Form.Item>
            </Col>
          </Row>
          <Button
            type="primary"
            htmlType="submit"
            icon={<SearchOutlined />}
            loading={isFetching}
          >
            {t("graphRag.exploreButton")}
          </Button>
        </Form>
      </Card>

      {!hasQuery && (
        <Card>
          <Empty description={t("graphRag.exploreHint")} />
        </Card>
      )}

      {isExample && hasQuery && (nodeCount > 0 || isFetching) && (
        <Text type="secondary">
          {t("graphRag.exampleHint", { gene: EXAMPLE_GENE })}
        </Text>
      )}

      {hasQuery && (isFetching || isPending) && !error && !hasGraph && (
        <div style={{ textAlign: "center", padding: 24 }}>
          <Spin size="large" />
          <Text type="secondary" style={{ display: "block", marginTop: 12 }}>
            {t("graphRag.exploreLoading")}
          </Text>
        </div>
      )}

      {hasQuery && error && !hasGraph && (
        <Card>
          <Text type="danger">
            {t("graphRag.error")}: {error.message}
          </Text>
        </Card>
      )}

      {hasQuery && !isFetching && !error && !hasGraph && (
        <Card>
          <Empty description={t("graphRag.exploreEmpty")} />
        </Card>
      )}

      {hasQuery && data && hasGraph && (
        <Card
          title={t("graphRag.graphTitle")}
          extra={
            <Text type="secondary">
              {t("graphRag.exploreCounts", { nodes: nodeCount, edges: edgeCount })}
            </Text>
          }
        >
          <KnowledgeGraphCanvas
            graph={data}
            height={560}
            onNodeClick={handleNodeClick}
          />
        </Card>
      )}

      <EntityDetailDrawer
        node={selectedNode}
        open={selectedNode !== null}
        onClose={() => setSelectedNode(null)}
      />
    </div>
  );
}
