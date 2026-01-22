import React, { useState } from "react";
import {
  Layout,
  Typography,
  Upload,
  Button,
  Progress,
  Card,
  Row,
  Col,
  Alert,
  Select,
  Space,
  Divider,
  Input,
} from "antd";
import {
  InboxOutlined,
  UploadOutlined,
  TranslationOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import "./App.css";

const { Header, Content, Footer } = Layout;
const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;
const { Dragger } = Upload;
const { Option } = Select;

interface TranslationTask {
  task_id: string;
  user_id: string;
  original_filename: string;
  detected_language: string | null;
  target_language: string;
  status: string;
  progress: number;
  character_count: number | null;
  created_at: string;
  preview_original: string | null;
  preview_translated: string | null;
}

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<TranslationTask | null>(null);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(
    null,
  );
  const [targetLanguage, setTargetLanguage] = useState<string>("en");
  const [directText, setDirectText] = useState<string>("");
  const [directTranslation, setDirectTranslation] = useState<string>("");

  const languageOptions = [
    { value: "en", label: "English" },
    { value: "zh", label: "Chinese" },
    { value: "ja", label: "Japanese" },
    { value: "ko", label: "Korean" },
    { value: "fr", label: "French" },
    { value: "de", label: "German" },
    { value: "es", label: "Spanish" },
  ];

  const handleFileUpload = async () => {
    if (!file) {
      alert("请先选择PDF文件");
      return;
    }

    setUploading(true);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("user_id", "demo-user-001");
    formData.append("target_language", targetLanguage);

    try {
      const response = await fetch("/api/translations/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("上传失败");
      }

      const task = await response.json();
      setTaskId(task.task_id);
      setTaskStatus(task);

      // 开始轮询任务状态
      startPolling(task.task_id);
    } catch (error) {
      console.error("上传失败:", error);
      alert("上传失败，请稍后重试");
    } finally {
      setUploading(false);
    }
  };

  const startPolling = (taskId: string) => {
    // 清除之前的轮询
    if (pollingInterval) {
      clearInterval(pollingInterval);
    }

    // 开始新的轮询
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`/api/translations/tasks/${taskId}`);
        if (!response.ok) {
          if (response.status === 404) {
            console.error("任务不存在，停止轮询:", taskId);
            clearInterval(interval);
            setPollingInterval(null);
            setTaskStatus((prev) =>
              prev ? { ...prev, status: "failed", progress: 100 } : null,
            );
          }
          throw new Error("获取任务状态失败");
        }

        const task = await response.json();
        setTaskStatus(task);

        // 如果任务完成或失败，停止轮询
        if (task.status === "completed" || task.status === "failed") {
          clearInterval(interval);
          setPollingInterval(null);
        }
      } catch (error) {
        console.error("轮询失败:", error);
      }
    }, 2000); // 每2秒轮询一次

    setPollingInterval(interval);
  };

  const handleDirectTranslate = async () => {
    if (!directText.trim()) {
      alert("请输入要翻译的文本");
      return;
    }

    const formData = new FormData();
    formData.append("text", directText);
    formData.append("target_language", targetLanguage);

    try {
      const response = await fetch("/api/translations/translate-text", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("翻译失败");
      }

      const result = await response.json();
      setDirectTranslation(result.translated_text);
    } catch (error) {
      console.error("翻译失败:", error);
      alert("翻译失败，请稍后重试");
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "pending":
        return "blue";
      case "processing":
        return "orange";
      case "translating":
        return "purple";
      case "completed":
        return "green";
      case "failed":
        return "red";
      default:
        return "gray";
    }
  };

  return (
    <Layout className="app-layout">
      <Header
        style={{
          background: "#fff",
          padding: "0 20px",
          boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
        }}
      >
        <Row align="middle" justify="space-between">
          <Col>
            <Space>
              <TranslationOutlined
                style={{ fontSize: "24px", color: "#1890ff" }}
              />
              <Title level={3} style={{ margin: 0 }}>
                多语种医学文献证据提取平台
              </Title>
            </Space>
          </Col>
          <Col>
            <Text type="secondary">基于ACMG-agent的文献证据提取</Text>
          </Col>
        </Row>
      </Header>

      <Content style={{ padding: "40px 50px" }}>
        <Row gutter={[32, 32]}>
          {/* PDF上传翻译区域 */}
          <Col xs={24} lg={12}>
            <Card
              title="PDF文档翻译"
              variant="borderless"
              extra={
                <Select
                  value={targetLanguage}
                  onChange={setTargetLanguage}
                  style={{ width: 120 }}
                >
                  {languageOptions.map((lang) => (
                    <Option key={lang.value} value={lang.value}>
                      {lang.label}
                    </Option>
                  ))}
                </Select>
              }
            >
              <Paragraph>
                上传PDF文档，系统将自动解析、检测语言并翻译成
                <Text strong>
                  {" "}
                  {
                    languageOptions.find((l) => l.value === targetLanguage)
                      ?.label
                  }{" "}
                </Text>
              </Paragraph>

              <Dragger
                accept=".pdf"
                beforeUpload={(file) => {
                  setFile(file);
                  return false; // 阻止自动上传
                }}
                showUploadList={false}
                maxCount={1}
              >
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p className="ant-upload-text">点击或拖拽PDF文件到此处</p>
                <p className="ant-upload-hint">支持单文件上传，最大50MB</p>
                {file && (
                  <Alert
                    message={`已选择: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`}
                    type="info"
                    showIcon
                    style={{ marginTop: 16 }}
                  />
                )}
              </Dragger>

              <Button
                type="primary"
                size="large"
                icon={<UploadOutlined />}
                loading={uploading}
                onClick={handleFileUpload}
                disabled={!file}
                style={{ marginTop: 24, width: "100%" }}
              >
                {uploading ? "上传中..." : "上传并翻译"}
              </Button>

              {/* 任务状态显示 */}
              {taskStatus && (
                <div style={{ marginTop: 32 }}>
                  <Title level={5}>翻译进度</Title>
                  <Card
                    style={{ marginTop: 16 }}
                    title={
                      <Space>
                        <Text>任务ID: </Text>
                        <Text code>{taskStatus.task_id}</Text>
                      </Space>
                    }
                    extra={
                      <Button
                        type="text"
                        icon={<EyeOutlined />}
                        onClick={() => startPolling(taskStatus.task_id)}
                      >
                        刷新
                      </Button>
                    }
                  >
                    <Space direction="vertical" style={{ width: "100%" }}>
                      <Row justify="space-between">
                        <Col>
                          <Text strong>文件: </Text>
                          <Text>{taskStatus.original_filename}</Text>
                        </Col>
                        <Col>
                          <Text strong>状态: </Text>
                          <Text
                            style={{
                              color: getStatusColor(taskStatus.status),
                            }}
                          >
                            {taskStatus.status.toUpperCase()}
                          </Text>
                        </Col>
                      </Row>

                      <Progress
                        percent={taskStatus.progress}
                        status={
                          taskStatus.status === "failed"
                            ? "exception"
                            : taskStatus.status === "completed"
                              ? "success"
                              : "active"
                        }
                      />

                      {taskStatus.detected_language && (
                        <Row justify="space-between">
                          <Col>
                            <Text strong>检测语言: </Text>
                            <Text>
                              {languageOptions.find(
                                (l) => l.value === taskStatus.detected_language,
                              )?.label || taskStatus.detected_language}
                            </Text>
                          </Col>
                          <Col>
                            <Text strong>目标语言: </Text>
                            <Text>
                              {languageOptions.find(
                                (l) => l.value === taskStatus.target_language,
                              )?.label || taskStatus.target_language}
                            </Text>
                          </Col>
                        </Row>
                      )}

                      {taskStatus.status === "failed" && (
                        <Alert
                          message="翻译失败"
                          description={
                            taskStatus.preview_original ||
                            "任务不存在或处理失败，请重试"
                          }
                          type="error"
                          showIcon
                          style={{
                            marginTop: 16,
                          }}
                        />
                      )}

                      {taskStatus.preview_translated && (
                        <>
                          <Divider />
                          <Title level={5}>翻译预览</Title>
                          <Card
                            style={{
                              background: "#f5f5f5",
                            }}
                          >
                            <Paragraph
                              style={{
                                whiteSpace: "pre-wrap",
                              }}
                            >
                              {taskStatus.preview_translated}
                            </Paragraph>
                            <Text
                              type="secondary"
                              style={{
                                fontSize: "12px",
                              }}
                            >
                              显示前500个字符，完整翻译将在完成后提供下载
                            </Text>
                          </Card>
                        </>
                      )}
                    </Space>
                  </Card>
                </div>
              )}
            </Card>
          </Col>

          {/* 直接文本翻译区域 */}
          <Col xs={24} lg={12}>
            <Card title="直接文本翻译" variant="borderless">
              <Paragraph>直接输入文本进行即时翻译，无需上传文件</Paragraph>

              <div style={{ marginBottom: 16 }}>
                <Text strong>目标语言: </Text>
                <Select
                  value={targetLanguage}
                  onChange={setTargetLanguage}
                  style={{ width: 120, marginLeft: 8 }}
                >
                  {languageOptions.map((lang) => (
                    <Option key={lang.value} value={lang.value}>
                      {lang.label}
                    </Option>
                  ))}
                </Select>
              </div>

              <TextArea
                placeholder="输入要翻译的文本..."
                value={directText}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                  setDirectText(e.target.value)
                }
                rows={8}
                style={{ marginBottom: 16 }}
              />

              <Button
                type="primary"
                size="large"
                icon={<TranslationOutlined />}
                onClick={handleDirectTranslate}
                disabled={!directText.trim()}
                style={{ width: "100%" }}
              >
                翻译文本
              </Button>

              {directTranslation && (
                <div style={{ marginTop: 32 }}>
                  <Title level={5}>翻译结果</Title>
                  <Card style={{ background: "#f0f9ff" }}>
                    <Paragraph style={{ whiteSpace: "pre-wrap" }}>
                      {directTranslation}
                    </Paragraph>
                    <Text type="secondary" style={{ fontSize: "12px" }}>
                      翻译完成
                    </Text>
                  </Card>
                </div>
              )}

              {/* 系统特性展示 */}
              <div style={{ marginTop: 48 }}>
                <Title level={5}>系统特性</Title>
                <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
                  <Col span={12}>
                    <Card size="small">
                      <Text strong>智能语言检测</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: "12px" }}>
                        自动识别文档语言
                      </Text>
                    </Card>
                  </Col>
                  <Col span={12}>
                    <Card size="small">
                      <Text strong>PDF解析</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: "12px" }}>
                        支持复杂PDF格式解析
                      </Text>
                    </Card>
                  </Col>
                  <Col span={12}>
                    <Card size="small">
                      <Text strong>LLM翻译</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: "12px" }}>
                        基于最新LLM模型的精准翻译
                      </Text>
                    </Card>
                  </Col>
                  <Col span={12}>
                    <Card size="small">
                      <Text strong>任务监控</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: "12px" }}>
                        实时进度跟踪和状态更新
                      </Text>
                    </Card>
                  </Col>
                </Row>
              </div>
            </Card>
          </Col>
        </Row>
      </Content>

      <Footer style={{ textAlign: "center" }}>
        多语种医学文献证据提取平台 ©2026 基于ACMG-agent的智能文档处理系统
      </Footer>
    </Layout>
  );
}

export default App;
