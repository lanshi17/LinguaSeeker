import { useMemo, useState } from "react";
import { App, Button, Dropdown, Form, Input, Modal, Typography } from "antd";
import type { MenuProps } from "antd";
import { ChevronDown, LogIn, LogOut, User } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useI18n } from "@/lib/i18n";
import { extractErrorMessage } from "@/lib/api/error";
import { login, logout } from "../services/auth";
import {
  PUBLIC_ACCOUNT,
  resetAccountScopedQueries,
  useAuthAccount,
} from "../hooks/useAuthAccount";
import type { AuthAccount } from "../types/auth";
import "./auth.css";

interface AuthFormValues {
  username: string;
  password: string;
}

function accountLabel(account: AuthAccount, publicLabel: string): string {
  if (account.account_type === "user") {
    return account.display_name || account.username || "Personal account";
  }
  return publicLabel;
}

export function AccountControl() {
  const { t } = useI18n();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const { data: account, isFetching } = useAuthAccount();
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm<AuthFormValues>();

  const activeAccount = account ?? PUBLIC_ACCOUNT;

  const completeAccountChange = (nextAccount: AuthAccount, successText: string) => {
    resetAccountScopedQueries(queryClient, nextAccount);
    setModalOpen(false);
    form.resetFields();
    message.success(successText);
  };

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: (result) => completeAccountChange(result.account, t("auth.loginSuccess")),
    onError: (error) => {
      message.error(extractErrorMessage(error, t("auth.loginFailed")));
    },
  });

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => completeAccountChange(PUBLIC_ACCOUNT, t("auth.logoutSuccess")),
    onError: (error) => {
      message.error(extractErrorMessage(error, t("auth.logoutFailed")));
    },
  });

  const openAuthModal = () => {
    setModalOpen(true);
    form.resetFields();
  };

  const menuItems = useMemo<MenuProps["items"]>(() => {
    const label = accountLabel(activeAccount, t("auth.publicAccount"));
    if (activeAccount.account_type === "user") {
      return [
        {
          key: "identity",
          disabled: true,
          label: (
            <div className="auth-menu-identity">
              <span>{label}</span>
              {activeAccount.username ? <small>{activeAccount.username}</small> : null}
            </div>
          ),
        },
        { type: "divider" },
        {
          key: "logout",
          icon: <LogOut size={16} />,
          label: t("auth.logout"),
        },
      ];
    }
    return [
      {
        key: "identity",
        disabled: true,
        label: (
          <div className="auth-menu-identity">
            <span>{t("auth.publicAccount")}</span>
            <small>{t("auth.publicScope")}</small>
          </div>
        ),
      },
      { type: "divider" },
      {
        key: "login",
        icon: <LogIn size={16} />,
        label: t("auth.loginOrCreate"),
      },
    ];
  }, [activeAccount, t]);

  const handleMenuClick: MenuProps["onClick"] = ({ key }) => {
    if (key === "login") openAuthModal();
    if (key === "logout") logoutMutation.mutate();
  };

  const handleSubmit = (values: AuthFormValues) => {
    loginMutation.mutate({
      username: values.username.trim(),
      password: values.password,
    });
  };

  const submitting = loginMutation.isPending;
  const label = accountLabel(activeAccount, t("auth.publicAccount"));

  return (
    <>
      <Dropdown
        trigger={["click"]}
        menu={{ items: menuItems, onClick: handleMenuClick }}
        placement="bottomRight"
      >
        <Button
          className="auth-account-button"
          loading={isFetching || logoutMutation.isPending}
          icon={<User size={16} />}
          type="text"
          aria-label={t("auth.accountMenu")}
        >
          <span className="auth-account-label">{label}</span>
          <ChevronDown className="auth-account-chevron" size={14} />
        </Button>
      </Dropdown>

      <Modal
        open={modalOpen}
        title={t("auth.loginOrCreateTitle")}
        footer={null}
        onCancel={() => setModalOpen(false)}
        destroyOnHidden
      >
        <div className="auth-modal-body">
          <Typography.Text type="secondary" className="auth-scope-note">
            {t("auth.personalScope")}
          </Typography.Text>
          <Form form={form} layout="vertical" onFinish={handleSubmit} requiredMark={false}>
            <Form.Item
              name="username"
              label={t("auth.username")}
              rules={[
                { required: true, message: t("auth.usernameRequired") },
              ]}
            >
              <Input autoComplete="username" placeholder={t("auth.usernamePlaceholder")} />
            </Form.Item>

            <Form.Item
              name="password"
              label={t("auth.password")}
              rules={[
                { required: true, message: t("auth.passwordRequired") },
              ]}
            >
              <Input.Password autoComplete="current-password" />
            </Form.Item>

            <Button type="primary" htmlType="submit" block loading={submitting}>
              {t("auth.loginOrCreateSubmit")}
            </Button>
          </Form>
        </div>
      </Modal>
    </>
  );
}
