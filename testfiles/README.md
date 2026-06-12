# Bulk Rename Py - Tests

## Test Overview

- File renaming operations
- Token replacement and slicing
- Case transformations
- Path validation
- Conflict detection
- Regex replacements
- Edge cases handled

## Requirements

```bash
pip install pytest
```

## Run Tests

### All tests
```bash
python -m pytest testfiles/ -v
```

### Specific test
```bash
python -m pytest testfiles/test_renamer.py::TestRenamer::test_preview_names_basic -v
```

## Expected Results

```
22 passed, 1 skipped
```