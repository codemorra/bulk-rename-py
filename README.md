# Bulk Rename Py

**Bulk Rename Py** is a Python application for **renaming files in bulk**.

It provides a wide range of features for conveniently renaming large numbers of files, including instant previews, an undo function, and support for freely combinable naming patterns.

![Screenshot of Bulk Rename Py main window](assets/screenshots/mainwindow.png)

---

## Table of Contents
- [Technical Requirements](#technical-requirements)
- [Installation](#installation)
- [Updates](#updates)
- [Function Overview](#function-overview)
- [Usage & Features](#usage--features)
- [Behavior & Notes](#behavior--notes)
- [License](#license)

---



## Technical Requirements
<a name="technical-requirements"></a>

### Manual installation

- **Python:** **>= 3.14**
- **Dependencies:** see [`requirements.txt`](requirements.txt)

### Prebuilt packages

- **AUR (Linux):** Python and dependencies are provided by the system package manager
- **Windows:** All required runtime files are included in the release archive

### Operating systems

- Linux (tested on Arch Linux)
- Windows (tested on Windows 11)

---

## Installation
<a name="installation"></a>

### AUR

The application is available in the Arch User Repository and can be installed using your preferred AUR helper, for example:

```bash
yay -S bulk-rename-py
```

### Windows

The [latest release](https://github.com/codemorra/bulk-rename-py/releases/latest) provides a `.zip` archive containing a Windows executable along with all required runtime files.

### Manually – Linux (without AUR)

1. Clone the repository:
   ```bash
   git clone https://github.com/codemorra/bulk-rename-py.git
   cd bulk-rename-py
   ```

2. Set up the virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   chmod +x start_linux.sh
   ./start_linux.sh
   ```

#### Optional: Create a Desktop Shortcut (desktop environments with .desktop files)

1. Copy the provided `.desktop` file from the repository to the appropriate directory:

    ```bash
    cp packaging/linux/bulk-rename-py.desktop ~/.local/share/applications/
    ```

2. Copy the icon files to the corresponding hicolor directories:

    ```bash
    for s in 16 32 64 128 256 512; do
        install -Dm644 assets/icons/png/bulk-rename-py_${s}.png ~/.local/share/icons/hicolor/${s}x${s}/apps/bulk-rename-py.png
    done
    ```

3. Open the copied file (`~/.local/share/applications/bulk-rename-py.desktop`) and adjust **Exec** and **TryExec** to your local installation path, for example:

    ```ini
    Exec='<PATH_TO_REPOSITORY>/.venv/bin/python3' '<PATH_TO_REPOSITORY>/src/main.py'
    TryExec=<PATH_TO_REPOSITORY>/.venv/bin/python3
    ```

4. Make the file executable:

    ```bash
    chmod +x ~/.local/share/applications/bulk-rename-py.desktop
    ```

    The application should now appear in the application menu.

### Manually - Windows

1. Clone the repository:
   ```bash
   git clone https://github.com/codemorra/bulk-rename-py.git
   cd bulk-rename-py
   ```

2. Set up the virtual environment (once):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   start_windows.bat
   ```

#### Optional: Create a Desktop Shortcut

1. Right-click on the desktop → New → Shortcut
    - Target:
      ```
      "<PATH_TO_REPOSITORY>\.venv\Scripts\pythonw.exe" "<PATH_TO_REPOSITORY>\src\main.py"
      ```

2. Right-click the shortcut → Properties → Change Icon...
    - Select icon:
      ```
      <PATH_TO_REPOSITORY>\assets\icons\bulk-rename-py.ico
      ```

---

## Updates
<a name="updates"></a>

You can check for available updates in the About dialog. If an update is available, it will be indicated next to the version number.

When installed via the AUR, updates are handled automatically by the package manager.

On Windows, the [latest release](https://github.com/codemorra/bulk-rename-py/releases/latest) can be downloaded as a `.zip` archive from the Releases section.

For manual installations, updates can be applied as follows:
```bash
git pull
pip install -r requirements.txt --upgrade
```

---

## Function Overview
<a name="function-overview"></a>

- **Filename & Extension Editing:** Independent editing of names and extensions
- **Flexible Replacement:** Replace entire names or selected parts
- **Preview Workflow:** See changes before applying them
- **Undo Functionality:** Revert changes if needed
- **Search & Replace:** With wildcards, regex, and advanced options
- **Automatic Counter:** Configurable numbering with duplicates handling
- **Date/Time Placeholders:** Predefined and custom formats
- **Case Transformation:** Uppercase, lowercase, heading, and mocking case
- **Windows Compatibility:** Automatic sanitization of filenames
- **External Editor:** Manual adjustments in text editor
- **Validation:** Duplicate detection and filename length checks
- Preview-based workflow:
  - Current filenames are shown on the left
  - New filenames are shown on the right
  - Changes are applied only after confirmation

---

## Usage & Features
<a name="usage--features"></a>

### Filename & Extension Editing

#### **Basic Placeholders**
- `{name}`, `{nameX-Y}`: Current filename (full or sliced)
- `{ext}`, `{extX-Y}`: File extension (full or sliced)
- `{counter}`: Auto-incrementing counter
- `{date}`: Configurable date format (YYYYMMDD, DDMMYYYY, etc.)
- `{time}`: Configurable time format (HHMMSS, HHMM, etc.)

**Custom Patterns (manual entry):**
- Dates: `{yyyy-mm-dd}`, `{dd.mm.yyyy}`, `{yyyy dd mm}`, `{mm;dd;yyyy}`, `{yyyy_mm},`, `{mm:yyyy}`, `{yyyy}`
- Times: `{hh-mm-ss}`, `{hh.mm}`, `{hhmmss}`
- Separators: `-`, `_`, `.`, `:`, `;`, ` ` (space), or none  
  - *Note: On Windows, `:` separators are automatically replaced with `_`* 

### **Search & Replace**
- **Wildcards:**
  - `*` = everything between first and next occurrence
  - `**` = everything between first and last occurrence
  - `?` = single character
- **Options:**
  - Regex mode
  - Case sensitivity
  - Exact matching
  - Replace first match only
  - Exclude extensions

### **Counter**
- Start value, increment, and digit width configurable
- Option to number only duplicates

### **Case Transformation**
- Lowercase, uppercase, heading case, or mocking case
- Applies to filenames (extensions remain unchanged)

### **Windows Compatibility**
- Removes/replaces invalid characters: `<>:"\|?*`
- Prevents reserved names: `CON`, `PRN`, `AUX`, `NUL`, etc.
- Always enabled on Windows, optional on Linux

### **Advanced Features**
- **External Editor:** Edit preview list in text editor
- **Validation:** Checks for duplicates and invalid filenames
- **Undo History:** Revert changes until file list is modified
---

### Additional features

- Import individual files or entire directories
- Option to include hidden files
- Drag & drop support from the file manager
- Detection of duplicate or invalid target filenames
- Undo functionality
- Available languages: German and English

---

## Behavior & Notes
<a name="behavior--notes"></a>

- **Filename length checks:** automatic validation for maximum filename length (Windows) and byte length (Linux)
- **Windows-compatible naming:** always enabled on Windows, optional on Linux
- **.lnk directory shortcuts (Windows):** can only be added via *Add folder*; using *Add file(s)* opens the target directory instead
- **External editor workflow:** changes are applied only after saving the edited file
- **Undo function:** the undo history is cleared if the file list is modified, cleared, or if the application is closed

---

## :warning: Important Safety Notice :warning:

### Always create a backup before renaming files!

While the application does not overwrite files automatically, unexpected issues (e.g. special characters or file permission problems) may still occur.

**The developer assumes no responsibility for data loss.**

---

## License
<a name="license"></a>

This project is licensed under the **MIT License**.  
See [`LICENSE`](LICENSE) for the full license text.

Third-party libraries used by this project are licensed under their respective licenses.  
All third-party license texts are collected in [`THIRD_PARTY_LICENSES.txt`](THIRD_PARTY_LICENSES.txt).

---

## Developer & Project Page

**Developer:** Codemorra (Christopher Kranz)  
**Project Page:** [https://github.com/codemorra/bulk-rename-py](https://github.com/codemorra/bulk-rename-py)  
© 2026-present Codemorra – All rights reserved.
