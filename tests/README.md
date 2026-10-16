# Bulk Rename Py - Tests

## Test Overview

- File renaming operations, name swaps, and rename chains
- Rollback after staging and destination failures
- Table and undo history after incomplete rollback
- Destination conflicts, including files created during execution
- Token replacement and slicing
- Case transformations
- Path validation
- Conflict detection
- Regex replacements
- Consistent date/time tokens and one modification-time read per file
- Duplicate numbering after replacement, sanitization, and extension changes
- Shared validation of generated and externally edited names
- Context menu, import cancellation, drag-and-drop, and undo button state
- Pending preview updates before rename and editor export
- Editor retry, cancellation, encoding, and temporary file cleanup
- Independent core imports without Qt, requests, or license resources
- Atomic settings writes, configuration validation, and shared counter ranges
- File collection options, path aliases, and numeric release validation
- Edge cases handled

## Requirements

```bash
python -m pip install -r requirements.txt -r tests/requirements.txt
```

## Run Tests

### All tests
Run from the repository root. The root-level `pyproject.toml` configures test discovery
and the source import path.

```bash
python -m pytest
```

### Specific test
```bash
python -m pytest tests/test_renamer.py::TestRenamer::test_preview_names_basic -v
```

## Regression Tests

`test_regressions.py` records confirmed issues in file preservation, duplicate
numbering, regex options, filename validation, and Windows preflight validation.
All recorded regression tests now pass without expected-failure markers.

File operation tests use temporary directories and verify file contents. The
Windows preflight test simulates the platform check without opening GUI dialogs;
it does not replace testing the application on Windows.

`test_file_operations.py` injects failures during execution and rollback and
checks the reported recovery paths. GUI tests use real Qt widgets with the
offscreen platform plugin and intercept dialogs and editor launches.

`test_rename_manager.py` covers file locations and undo history after failures.
`test_gui_workflows.py` covers table actions, imports, and the editor workflow.
It also creates the complete main window with settings redirected to a temporary
directory and exercises import, rename, undo, row removal, and clearing. These
tests do not read or write user settings or launch an external editor.

`test_name_generation.py` checks combined naming options, regex errors, timestamp
consistency across midnight, and reuse of file metadata and prepared search
patterns. Filename validation also covers UTF-8 byte limits and Windows UTF-16
code-unit limits.

`test_settings.py` checks preservation of existing configuration files after
write failures. Its window test uses temporary settings and checks shared GUI
instances and counter limits. `test_importer.py` covers collection and visibility
options. `test_update_checker.py` uses mocked responses and makes no network
requests.

`test_module_imports.py` also runs a subprocess without site packages to verify
core imports. Its icon check renders the SVG resource from `src/resources/` with
PySide6 Essentials; the Addons package is not required.

## Lint Checks

Ruff is included in `tests/requirements.txt`. Its Python target is configured in
`pyproject.toml`; compiled Qt resource code is excluded because it is generated.
Check application code and tests with:

```bash
python -m ruff check src tests
```
