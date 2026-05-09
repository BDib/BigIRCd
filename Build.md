# BigIRCd Build & Compilation Guide

This document outlines the process of compiling the BigIRCd Python source code into a high-performance, standalone Windows executable using **Cython** for C-compilation and **PyInstaller** for bundling.

## 🏗️ Compilation Strategy

To achieve near-native performance and protect the source code, we use a two-stage build process:

1. **Cython Conversion**: Translates `.py` logic into `.c` source code and compiles it into machine-code binary extensions (`.pyd`).
2. **PyInstaller Bundling**: Packages the compiled binaries, the Python runtime, and static assets (like `motd.txt`) into a single `.exe`.

---

## 🛠️ Prerequisites

* **Python 3.8+**
* **C Compiler**: [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (Required for Cython on Windows).
* **Required Packages**:
  
  ```bash
  pip install cython pyinstaller setuptools
  ```

---

## 1. The Build Script (`setup.py`)

We centralized all core logic into a compilation list. The `Utils.py` module is compiled first to ensure all other modules can link to its C-extension for path-finding and IRC logic.

```python
from setuptools import setup
from Cython.Build import cythonize

modules = [
    "Utils.py",
    "Database.py",
    "Channel.py",
    "Client.py",
    "Server.py"
]

setup(
    name='BigIRCd',
    ext_modules=cythonize(modules, compiler_directives={'language_level': "3"}),
)
```

**To generate C-extensions, run:**

```bash
python setup.py build_ext --inplace
```

This produces `.pyd` files which are your Python modules compiled into C.

---

## 2. Path Management Logic

Because PyInstaller unpacks files into a temporary directory (`_MEIPASS`), we implemented a dual-path strategy in `Utils.py` to handle resources vs. persistent data:

* **Resources (`motd.txt`)**: Located inside the internal bundle using `resource_path()`.
* **Persistent Data (`bigircd.db`)**: Located in the same folder as the `.exe` using `data_path()`.

```python
# Path-finding implementation in Utils.py
def get_base_path(is_resource=True):
    if is_resource:
        return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.dirname(sys.executable)
```

---

## 3. Creating the Executable (`PyInstaller`)

Once the C-extensions are built, we bundle the entry point (`Main.py`) and the static assets.

**Command:**

```bash
pyinstaller --onefile --add-data "motd.txt;." Main.py
```

* `--onefile`: Compresses everything into a single `Main.exe`.
* `--add-data "motd.txt;."`: Includes the welcome art inside the executable.
* **Note**: We do **not** bundle `bigircd.db`. The server will automatically create a persistent database in the same directory as the `.exe` upon its first run.

---

## 🎨 Customization
* **Icon**: Place a `.ico` file in `assets/icon.ico`.
* **Output Name**: Controlled via the `--name` flag in PyInstaller.
* **Command**: 
  pyinstaller --onefile --name "BigIRCd" --icon "assets/icon.ico" --add-data "motd.txt;." Main.py

## 🚀 Final Output

The resulting executable can be found in the `dist/` folder.

* **Performance**: Core logic runs as compiled C code.
* **Portability**: No Python installation is required on the target machine.
* **Persistence**: Settings and registrations are saved to `bigircd.db` located alongside the executable.

### Key Sections Included:

* **Compilation Strategy**: Explains the two-stage process using **Cython** for performance and **PyInstaller** for bundling.
* **Build Script Setup**: Outlines the `setup.py` configuration used to compile `Utils.py`, `Database.py`, `Channel.py`, `Client.py`, and `Server.py` into binary extensions.
* **Path Management**: Documents the dual-path logic (Resources vs. Persistent Data) implemented to handle the unique runtime environment of a bundled executable.
* **Packaging**: Provides the exact CLI commands used to generate the final `Main.exe`