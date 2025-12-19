#!/usr/bin/env python3
"""
檢查並修復專案中重複的 BizException 錯誤代碼

功能:
1. 掃描 ERROR_ 常數定義 (private static final long ERROR_XXX = 202511250001L;)
2. 掃描內嵌式 BizException.failed(數字L, ...) 調用
3. 檢測重複的錯誤代碼
4. 自動生成唯一的替換代碼

使用方式:
    python fix_duplicate_biz_exception_codes.py           # 僅檢查重複
    python fix_duplicate_biz_exception_codes.py --fix     # 檢查並修復重複
"""

import re
import os
import glob
from collections import defaultdict
from datetime import datetime
import argparse


class ErrorCodeLocation:
    """表示錯誤代碼的位置資訊"""
    def __init__(self, file_path, line_num, line_content, constant_name=None, is_constant_def=False):
        self.file_path = file_path
        self.line_num = line_num
        self.line_content = line_content
        self.constant_name = constant_name  # ERROR_XXX 常數名稱
        self.is_constant_def = is_constant_def  # 是否為常數定義行

    def __repr__(self):
        return f"{self.file_path}:{self.line_num}"


def find_all_error_codes(project_root):
    """
    掃描專案中所有錯誤代碼

    搜尋兩種模式:
    1. 常數定義: private static final long ERROR_XXX = 202511250001L;
    2. 內嵌調用: BizException.failed(202511250001L, ...)

    Returns:
        dict: {error_code: [ErrorCodeLocation, ...]}
    """
    # 模式1: 常數定義
    constant_pattern = re.compile(
        r'private\s+static\s+final\s+long\s+(ERROR_\w+)\s*=\s*(\d+)L?\s*;'
    )

    # 模式2: 內嵌式 BizException.failed 調用 (直接使用數字)
    inline_pattern = re.compile(
        r'BizException\.failed\s*\(\s*(\d+)L?\s*,'
    )

    code_locations = defaultdict(list)

    # 目標目錄
    target_dirs = [
        'cage-features/src/main/java',
        'gaming-table-feature/src/main/java',
        'user-features/src/main/java',
        'common-shared/src/main/java',
        'login-feature/src/main/java',
        'image-feature/src/main/java',
        'shared-infrastructure/src/main/java',
    ]

    java_files = []
    for target_dir in target_dirs:
        full_path = os.path.join(project_root, target_dir)
        if os.path.exists(full_path):
            java_files.extend(glob.glob(os.path.join(full_path, '**', '*.java'), recursive=True))

    # 如果目標目錄不存在，fallback 到整個專案
    if not java_files:
        java_files = glob.glob(os.path.join(project_root, '**', '*.java'), recursive=True)

    for file_path in java_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line_num, line in enumerate(lines, 1):
                    # 搜尋常數定義
                    const_matches = constant_pattern.findall(line)
                    for const_name, code in const_matches:
                        location = ErrorCodeLocation(
                            file_path=file_path,
                            line_num=line_num,
                            line_content=line.strip(),
                            constant_name=const_name,
                            is_constant_def=True
                        )
                        code_locations[code].append(location)

                    # 搜尋內嵌式調用 (排除已經是用常數的情況)
                    # 檢查是否使用常數 (如 ERROR_XXX) 而非直接數字
                    if 'BizException.failed(' in line:
                        # 檢查是否使用 ERROR_ 常數
                        if not re.search(r'BizException\.failed\s*\(\s*ERROR_', line):
                            inline_matches = inline_pattern.findall(line)
                            for code in inline_matches:
                                location = ErrorCodeLocation(
                                    file_path=file_path,
                                    line_num=line_num,
                                    line_content=line.strip(),
                                    constant_name=None,
                                    is_constant_def=False
                                )
                                code_locations[code].append(location)

        except Exception as e:
            print(f"警告: 無法讀取文件 {file_path}: {e}")

    return code_locations


def find_duplicates(code_locations):
    """
    找出重複的錯誤代碼

    Returns:
        dict: {error_code: [ErrorCodeLocation, ...]} (只包含重複的)
    """
    return {code: locations for code, locations in code_locations.items() if len(locations) > 1}


def get_all_existing_codes(code_locations):
    """取得所有已存在的錯誤代碼"""
    return set(code_locations.keys())


def generate_new_code(existing_codes, base_date=None):
    """
    生成一個新的唯一錯誤代碼
    格式: YYYYMMDDNNNN (12位數字)

    例如: 202512180001
    """
    if base_date is None:
        base_date = datetime.now()

    # 使用日期前綴 + 4位序號
    date_prefix = base_date.strftime('%Y%m%d')

    counter = 1
    while True:
        new_code = f"{date_prefix}{counter:04d}"
        if new_code not in existing_codes:
            return new_code
        counter += 1
        if counter > 9999:
            # 如果超過9999，使用更長格式
            new_code = f"{date_prefix}{counter:06d}"
            if new_code not in existing_codes:
                return new_code


def fix_duplicates(project_root, duplicates, existing_codes, dry_run=False):
    """
    修復重複的錯誤代碼

    策略:
    - 對於常數定義重複: 修改常數的值
    - 對於內嵌式重複: 修改數字值
    - 保留第一個出現的位置，替換其他位置為新代碼

    Returns:
        list of (file_path, line_num, old_code, new_code, constant_name)
    """
    changes = []
    all_codes = set(existing_codes)

    for code, locations in duplicates.items():
        # 按文件名排序，保持一致性
        sorted_locations = sorted(locations, key=lambda loc: (loc.file_path, loc.line_num))

        # 保留第一個位置，替換其餘的
        for location in sorted_locations[1:]:
            new_code = generate_new_code(all_codes)
            all_codes.add(new_code)
            changes.append((
                location.file_path,
                location.line_num,
                code,
                new_code,
                location.constant_name,
                location.is_constant_def,
                location.line_content
            ))

    if dry_run:
        return changes

    # 按文件分組變更
    file_changes = defaultdict(list)
    for file_path, line_num, old_code, new_code, const_name, is_const_def, _ in changes:
        file_changes[file_path].append((line_num, old_code, new_code, const_name, is_const_def))

    # 應用變更
    for file_path, line_changes in file_changes.items():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line_num, old_code, new_code, const_name, is_const_def in line_changes:
                idx = line_num - 1
                original_line = lines[idx]

                if is_const_def and const_name:
                    # 替換常數定義中的值
                    # private static final long ERROR_XXX = 202511250001L;
                    old_pattern = f'{old_code}L'
                    new_pattern = f'{new_code}L'
                    lines[idx] = original_line.replace(old_pattern, new_pattern, 1)
                else:
                    # 替換內嵌式調用中的值
                    old_pattern = f'BizException.failed({old_code}L,'
                    new_pattern = f'BizException.failed({new_code}L,'
                    if old_pattern in original_line:
                        lines[idx] = original_line.replace(old_pattern, new_pattern, 1)
                    else:
                        # 嘗試沒有 L 後綴的模式
                        old_pattern = f'BizException.failed({old_code},'
                        new_pattern = f'BizException.failed({new_code}L,'
                        lines[idx] = original_line.replace(old_pattern, new_pattern, 1)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            relative_path = os.path.relpath(file_path, project_root)
            print(f"已更新文件: {relative_path}")
            for line_num, old_code, new_code, const_name, is_const_def in line_changes:
                if const_name:
                    print(f"  行 {line_num}: {const_name} = {old_code}L -> {new_code}L")
                else:
                    print(f"  行 {line_num}: {old_code}L -> {new_code}L")

        except Exception as e:
            print(f"錯誤: 無法更新文件 {file_path}: {e}")

    return changes


def print_report(project_root, code_locations, duplicates):
    """輸出詳細報告"""
    print("=" * 70)
    print("BizException 錯誤代碼檢查報告")
    print("=" * 70)
    print()

    # 統計
    total_codes = len(code_locations)
    total_locations = sum(len(locs) for locs in code_locations.values())
    constant_defs = sum(1 for locs in code_locations.values()
                        for loc in locs if loc.is_constant_def)
    inline_calls = total_locations - constant_defs

    print(f"掃描結果:")
    print(f"  - 不同錯誤代碼數量: {total_codes}")
    print(f"  - 總出現次數: {total_locations}")
    print(f"  - 常數定義 (ERROR_XXX): {constant_defs}")
    print(f"  - 內嵌式調用: {inline_calls}")
    print()

    if not duplicates:
        print("✅ 沒有發現重複的錯誤代碼")
        return

    print(f"⚠️  發現 {len(duplicates)} 個重複的錯誤代碼:\n")

    for code, locations in sorted(duplicates.items()):
        print("-" * 50)
        print(f"錯誤代碼: {code}L (出現 {len(locations)} 次)")
        print()

        for i, loc in enumerate(locations):
            relative_path = os.path.relpath(loc.file_path, project_root)
            marker = "🔒 保留" if i == 0 else "🔄 需修改"

            if loc.constant_name:
                print(f"  {marker} {relative_path}:{loc.line_num}")
                print(f"         常數: {loc.constant_name}")
            else:
                print(f"  {marker} {relative_path}:{loc.line_num}")
                print(f"         (內嵌式調用)")

            # 顯示代碼片段
            line_preview = loc.line_content[:80]
            if len(loc.line_content) > 80:
                line_preview += "..."
            print(f"         代碼: {line_preview}")
            print()

    print("-" * 50)


def main():
    parser = argparse.ArgumentParser(
        description='檢查並修復重複的 BizException 錯誤代碼',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
    python fix_duplicate_biz_exception_codes.py           # 僅檢查重複
    python fix_duplicate_biz_exception_codes.py --fix     # 檢查並修復重複
    python fix_duplicate_biz_exception_codes.py --root /path/to/project
        """
    )
    parser.add_argument('--fix', action='store_true',
                        help='自動修復重複的錯誤代碼')
    parser.add_argument('--root', default='.',
                        help='專案根目錄 (預設: 當前目錄)')
    args = parser.parse_args()

    project_root = os.path.abspath(args.root)
    print(f"掃描專案: {project_root}\n")

    # 找出所有錯誤代碼
    code_locations = find_all_error_codes(project_root)

    # 找出重複的
    duplicates = find_duplicates(code_locations)

    # 輸出報告
    print_report(project_root, code_locations, duplicates)

    if not duplicates:
        return 0

    if args.fix:
        print("\n" + "=" * 70)
        print("開始修復重複的錯誤代碼...")
        print("=" * 70 + "\n")

        existing_codes = get_all_existing_codes(code_locations)
        changes = fix_duplicates(project_root, duplicates, existing_codes)

        print()
        print("=" * 70)
        print(f"✅ 完成! 共修復 {len(changes)} 處重複的錯誤代碼")
        print("=" * 70)
    else:
        print("\n💡 提示: 使用 --fix 參數來自動修復重複的錯誤代碼")
        print("   範例: python fix_duplicate_biz_exception_codes.py --fix")

    return 1 if duplicates else 0


if __name__ == '__main__':
    exit(main())
