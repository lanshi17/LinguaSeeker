"""
ACMG-PS3 智能评级系统 - 后端核心模块

该模块包含了系统的四个核心层：
- database: 数据访问层，包含各种数据库客户端和服务
- domain: 领域层，包含业务逻辑和核心模型
- presentation: 表现层，包含API接口定义
- service: 服务层，包含应用服务和业务协调
- utils: 工具层，包含通用工具函数和辅助类
"""

# 导入核心配置
from .config import settings

__all__ = [
    "settings",
]

# 版本信息
__version__ = "1.0.0"