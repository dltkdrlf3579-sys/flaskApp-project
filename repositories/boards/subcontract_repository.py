"""Repositories for subcontract-related dynamic boards."""

from __future__ import annotations

from repositories.boards.follow_sop_repository import DynamicBoardRepository


class SubcontractApprovalRepository(DynamicBoardRepository):
    """Repository for the 산안법 도급승인 보드."""

    board_type = "subcontract_approval"

    default_sections = [("basic_info", "기본정보", 1)]

    def ensure_default_sections(self) -> None:
        with self.connection() as conn:
            cursor = conn.cursor()
            for key, name, order in self.default_sections:
                cursor.execute(
                    f"""
                    INSERT INTO {self.section_table} (section_key, section_name, section_order, is_active, is_deleted)
                    VALUES (%s, %s, %s, 1, 0)
                    ON CONFLICT (section_key) DO NOTHING
                    """,
                    (key, name, order),
                )
            conn.commit()


class SubcontractReportRepository(DynamicBoardRepository):
    """Repository for the 화관법 도급신고 보드."""

    board_type = "subcontract_report"

    default_sections = [("basic_info", "기본정보", 1)]

    def ensure_default_sections(self) -> None:
        with self.connection() as conn:
            cursor = conn.cursor()
            for key, name, order in self.default_sections:
                cursor.execute(
                    f"""
                    INSERT INTO {self.section_table} (section_key, section_name, section_order, is_active, is_deleted)
                    VALUES (%s, %s, %s, 1, 0)
                    ON CONFLICT (section_key) DO NOTHING
                    """,
                    (key, name, order),
                )
            conn.commit()
