# CMS Python Tools

A collection of Python utilities for managing Java exception handling and error codes in CMS projects.

## Scripts

### convert_exceptions.py

Automates conversion of exception handling patterns in Java code to use `BizException.failed()`.

**Features:**
- Converts `throw new IllegalArgumentException(...)` to `throw BizException.failed(code, ...)`
- Converts `BizException.badRequest(...)` to `BizException.failed(code, ...)`
- Updates JavaDoc `@throws IllegalArgumentException` annotations to `@throws BizException`
- Automatically adds the required `BizException` import statement if not present
- Assigns unique error codes with date prefix (YYYYMMDD format)

**Usage:**
```bash
python convert_exceptions.py [options]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--date` | Date prefix for error codes (default: today) |
| `--dry-run` | Preview changes without modifying files |
| `--dirs` | Specify target directories to scan |
| `--start-counter` | Starting number for error code sequence |

---

### fix_duplicate_biz_exception_codes.py

Detects and fixes duplicate error codes in `BizException` usage across the Java codebase.

**Features:**
- Scans for error code constants: `private static final long ERROR_XXX = 202511250001L;`
- Detects inline `BizException.failed()` calls with numeric error codes
- Identifies duplicate error codes used in multiple locations
- Automatically generates unique replacement codes using date-based format (YYYYMMDDNNNN)
- Provides detailed reporting with file locations and code snippets
- Supports dry-run mode for preview before applying fixes

**Usage:**
```bash
# Check for duplicates (read-only)
python fix_duplicate_biz_exception_codes.py

# Fix duplicates automatically
python fix_duplicate_biz_exception_codes.py --fix
```

**Options:**
| Option | Description |
|--------|-------------|
| `--fix` | Automatically fix duplicates (default is check-only mode) |
| `--root` | Specify project root directory (default: current directory) |

**Target Directories:**
- `cage-features/src/main/java`
- `gaming-table-feature/src/main/java`
- `user-features/src/main/java`
- `common-shared/src/main/java`
- `login-feature/src/main/java`
- `image-feature/src/main/java`
- `shared-infrastructure/src/main/java`
