# src/domain/literature/hans_publishers/enums.py
"""Enums for Hans Publishers service."""

from enum import Enum


class Subject(str, Enum):
    """Common subject areas for Hans Publishers."""

    # Natural Sciences
    MATHEMATICS = "数学"
    PHYSICS = "物理"
    CHEMISTRY = "化学"
    BIOLOGY = "生物"

    # Engineering
    COMPUTER_SCIENCE = "计算机"
    ELECTRONICS = "电子"
    MECHANICAL = "机械"
    CIVIL = "土木"

    # Medicine
    CLINICAL_MEDICINE = "临床医学"
    PHARMACY = "药学"
    PUBLIC_HEALTH = "公共卫生"

    # Social Sciences
    ECONOMICS = "经济"
    MANAGEMENT = "管理"
    LAW = "法律"
    EDUCATION = "教育"
