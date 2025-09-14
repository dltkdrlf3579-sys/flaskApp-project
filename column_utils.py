#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Common utilities for column type normalization across all boards.
This module eliminates code duplication in board register/detail routes.
"""

def determine_linked_type(col):
    """
    table_group과 table_type을 활용하여 정확한 linked 타입 결정

    Args:
        col: column dictionary with column_key, table_group, table_type

    Returns:
        str: specific linked type (linked_company, linked_employee, etc.)
    """
    column_key = col.get('column_key', '')
    table_group = col.get('table_group', '')
    table_type = col.get('table_type', '')

    # suffix가 있는 필드는 무조건 linked_text (table_group 기반 처리를 위해)
    suffixes = ['_bizno', '_company', '_dept', '_code', '_id']
    for suffix in suffixes:
        if column_key.endswith(suffix):
            return 'linked_text'

    # table_type 우선 확인 (가장 명확한 지표)
    if table_type:
        if table_type == 'company':
            return 'linked_company'
        elif table_type == 'employee':
            return 'linked_employee'
        elif table_type == 'partner':
            return 'linked_partner'
        elif table_type == 'contractor':
            return 'linked_contractor'
        elif table_type == 'department':
            return 'linked_department'

    # table_group 확인 (두 번째 우선순위)
    if table_group:
        # table_group이 베이스 필드와 연관되어 있으면 그 타입 사용
        if 'company' in table_group or 'add_company_info' in table_group:
            return 'linked_company'
        elif 'worker' in table_group or 'employee' in table_group:
            return 'linked_employee'
        elif 'partner' in table_group:
            return 'linked_partner'
        elif 'contractor' in table_group:
            return 'linked_contractor'
        elif 'department' in table_group or 'dept' in table_group:
            return 'linked_department'

    # 기본값
    return 'linked_text'


def normalize_column_types(columns):
    """
    Normalize column types for all columns in a board configuration.
    Handles both linked types and other column type transformations.

    Args:
        columns: list of column dictionaries from database

    Returns:
        list: columns with normalized types
    """
    for col in columns:
        column_key = col.get('column_key', '')
        column_type = col.get('column_type', '')

        # linked_text 타입 정규화
        if column_type == 'linked_text':
            col['column_type'] = determine_linked_type(col)

        # linked_dept 타입 정규화
        elif column_type == 'linked_dept':
            col['column_type'] = determine_linked_type(col)

        # 기타 linked 타입 정규화
        elif column_type == 'linked':
            col['column_type'] = determine_linked_type(col)

        # popup 타입이지만 suffix가 있는 경우 (잘못된 타입) linked로 변경
        elif column_type.startswith('popup_') and any(column_key.endswith(suffix) for suffix in ['_company', '_bizno', '_id', '_dept', '_code']):
            col['column_type'] = determine_linked_type(col)

    return columns


def get_board_columns(cursor, config_table, is_active_only=True):
    """
    Get and normalize columns for a specific board.

    Args:
        cursor: database cursor
        config_table: name of the column config table
        is_active_only: whether to filter by is_active=1

    Returns:
        list: normalized column configurations
    """
    query = f"""
        SELECT * FROM {config_table}
        {' WHERE is_active=1' if is_active_only else ''}
        ORDER BY column_order
    """
    cursor.execute(query)
    columns = cursor.fetchall()

    # Convert to dictionaries
    column_dicts = []
    column_names = [desc[0] for desc in cursor.description]
    for row in columns:
        column_dicts.append(dict(zip(column_names, row)))

    # Normalize column types
    return normalize_column_types(column_dicts)


def prepare_columns_for_template(columns, data_row=None):
    """
    Prepare columns for template rendering with data values.

    Args:
        columns: list of normalized column configurations
        data_row: optional data row to merge with columns

    Returns:
        list: columns ready for template rendering
    """
    prepared_columns = []

    for col in columns:
        prepared_col = col.copy()

        # Add data value if available
        if data_row and col.get('column_key') in data_row:
            prepared_col['value'] = data_row[col['column_key']]

        # Handle special column types that need additional processing
        if col.get('column_type') in ['popup_company', 'popup_person', 'popup_department']:
            # Add any popup-specific configuration
            prepared_col['is_popup'] = True

        elif col.get('column_type').startswith('linked_'):
            # Add linked field configuration
            prepared_col['is_linked'] = True
            prepared_col['linked_to'] = col.get('linked_columns', '')

        prepared_columns.append(prepared_col)

    return prepared_columns