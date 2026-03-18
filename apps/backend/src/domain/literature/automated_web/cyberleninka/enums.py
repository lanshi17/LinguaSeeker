# src/domain/literature/cyberleninka/enums.py
"""Enums for CyberLeninka service."""

from enum import Enum


class Subject(str, Enum):
    """Common subject areas for CyberLeninka."""

    # Natural Sciences
    MATHEMATICS = "Математика"
    PHYSICS = "Физика"
    CHEMISTRY = "Химия"
    BIOLOGY = "Биология"

    # Engineering
    COMPUTER_SCIENCE = "Информатика"
    ELECTRONICS = "Электроника"
    MECHANICAL = "Механика"

    # Medicine
    MEDICINE = "Медицина"
    PHARMACY = "Фармация"

    # Social Sciences
    ECONOMICS = "Экономика"
    LAW = "Право"
    EDUCATION = "Педагогика"
    PHILOLOGY = "Филология"
    PHILOSOPHY = "Философия"
    HISTORY = "История"
