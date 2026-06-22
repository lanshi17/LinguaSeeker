# 这里放置真实部署时挂载到后端容器的 `production.yaml`。
#
# 文件路径：deploy/compose/backend-host/config/production.yaml
# 在容器内挂载为：/app/config/environments/production.yaml （只读）
#
# 参考模板：backend/config/environments/production.yaml.example
#
# vault 机密放在 ./vault/production.yaml，对应容器内
# /app/config/vault/production.yaml （只读，权限 0600）。
