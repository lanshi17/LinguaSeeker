import { useI18n } from "@/lib/i18n";
import { SendOutlined } from "@ant-design/icons";
import {
  Button,
  Card,
  Form,
  Input,
  Radio,
  Space,
  Spin,
  Typography,
} from "antd";
import { useState } from "react";
import { useGraphRagQuery } from "../hooks/useGraphRagQuery";
import { KnowledgeGraphCanvas } from "./KnowledgeGraphCanvas";

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

export function GraphRagView() {
  const { t } = useI18n();
  const [form] = Form.useForm();
  const [mode, setMode] = useState<"full" | "terminology_only">("full");
  const { mutateAsync, data, isPending, error } = useGraphRagQuery();

  const handleSubmit = async (values: { question: string }) => {
    await mutateAsync({
      question: values.question,
      hops: 2,
      mode,
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <Card>
        <Title level={4}>{t("graphRag.title")}</Title>
        <Paragraph type="secondary">{t("graphRag.description")}</Paragraph>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{ question: "" }}
        >
          <Form.Item
            name="question"
            label={t("graphRag.questionLabel")}
            rules={[
              { required: true, message: t("graphRag.questionRequired") },
            ]}
          >
            <TextArea
              rows={3}
              placeholder={t("graphRag.questionPlaceholder")}
              disabled={isPending}
            />
          </Form.Item>
          <Form.Item label={t("graphRag.modeLabel")}>
            <Radio.Group
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              disabled={isPending}
            >
              <Radio.Button value="full">{t("graphRag.modeFull")}</Radio.Button>
              <Radio.Button value="terminology_only">
                {t("graphRag.modeTerminology")}
              </Radio.Button>
            </Radio.Group>
          </Form.Item>
          <Space>
            <Button
              type="primary"
              htmlType="submit"
              icon={<SendOutlined />}
              loading={isPending}
            >
              {t("graphRag.askButton")}
            </Button>
          </Space>
        </Form>
      </Card>

      {isPending && (
        <div style={{ textAlign: "center", padding: 24 }}>
          <Spin size="large" />
          <Text type="secondary" style={{ display: "block", marginTop: 12 }}>
            {t("graphRag.thinking")}
          </Text>
        </div>
      )}

      {error && (
        <Card>
          <Text type="danger">
            {t("graphRag.error")}: {error.message}
          </Text>
        </Card>
      )}

      {data && (
        <>
          <Card title={t("graphRag.answerTitle")}>
            <Paragraph style={{ whiteSpace: "pre-wrap" }}>
              {data.answer}
            </Paragraph>
            {data.source_evidence_ids.length > 0 && (
              <Text type="secondary">
                {t("graphRag.sourceCount", {
                  count: data.source_evidence_ids.length,
                })}
              </Text>
            )}
          </Card>

          {data.subgraph.nodes.length > 0 && (
            <Card title={t("graphRag.graphTitle")}>
              <KnowledgeGraphCanvas graph={data.subgraph} height={560} />
            </Card>
          )}
        </>
      )}
    </div>
  );
}
