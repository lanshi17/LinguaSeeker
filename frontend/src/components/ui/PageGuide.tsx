import { Drawer, Collapse, Typography } from "antd";
import { useI18n } from "@/lib/i18n";

export interface GuideSection {
  title: string;
  items: string[];
}

interface PageGuideProps {
  open: boolean;
  onClose: () => void;
  title: string;
  sections: GuideSection[];
}

export function PageGuide({ open, onClose, title, sections }: PageGuideProps) {
  const { t } = useI18n();

  return (
    <Drawer
      title={title}
      open={open}
      onClose={onClose}
      placement="right"
      styles={{
        body: { padding: "8px 20px 20px" },
        wrapper: { width: 400 },
        header: { borderBottom: "1px solid var(--color-border)", padding: "12px 20px" },
      }}
    >
      <Collapse
        defaultActiveKey={sections.map((_, i) => String(i))}
        ghost
        style={{ background: "transparent" }}
        items={sections.map((section, idx) => ({
          key: String(idx),
          label: (
            <Typography.Text
              strong
              style={{
                fontSize: 12,
                fontWeight: 600,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                color: "var(--color-text-secondary)",
              }}
            >
              {section.title}
            </Typography.Text>
          ),
          children: (
            <ul
              style={{
                margin: 0,
                padding: "0 0 0 16px",
                display: "flex",
                flexDirection: "column",
                gap: 6,
              }}
            >
              {section.items.map((item, j) => (
                <li key={j} style={{ fontSize: 13, lineHeight: 1.6, color: "var(--color-text)" }}>
                  {item}
                </li>
              ))}
            </ul>
          ),
        }))}
      />

      <Typography.Text
        style={{
          display: "block",
          marginTop: 20,
          paddingTop: 12,
          borderTop: "1px solid var(--color-border)",
          fontSize: 11,
          color: "var(--color-text-muted)",
          textAlign: "center",
        }}
      >
        {t("pageGuide.footer")}
      </Typography.Text>
    </Drawer>
  );
}
