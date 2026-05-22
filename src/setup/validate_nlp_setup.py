"""
NLP Setup Validator
Automated validation of spaCy, MarkItDown, and token counting setup.
Checks system dependencies and provides detailed installation guidance.
"""

import platform
import subprocess
import sys
from typing import Any, Dict

# ANSI color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_status(status: str, component: str, details: str = "") -> None:
    """Print colored status message."""
    if status == "✅":
        print(f"{GREEN}{status}{RESET} {component}: {details}")
    elif status == "❌":
        print(f"{RED}{status}{RESET} {component}: {details}")
    elif status == "⚠️":
        print(f"{YELLOW}{status}{RESET} {component}: {details}")
    elif status == "ℹ️":
        print(f"{BLUE}{status}{RESET} {component}: {details}")


def validate_python_version() -> Dict[str, Any]:
    """Validate Python 3.12+ installation."""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    if version.major == 3 and version.minor >= 12:
        return {
            "status": "✅",
            "version": version_str,
            "detail": f"Python {version_str} is compatible",
        }
    else:
        return {
            "status": "❌",
            "version": version_str,
            "detail": f"Python {version_str} found, but 3.12+ required",
        }


def validate_spacy() -> Dict[str, Any]:
    """Validate spaCy 3.8.0+ installation and model."""
    try:
        import spacy

        version = spacy.__version__
        version_parts = version.split(".")[:2]
        major, minor = int(version_parts[0]), int(version_parts[1])

        if major < 3 or (major == 3 and minor < 8):
            return {
                "status": "❌",
                "version": version,
                "detail": f"spaCy {version} found, but 3.8.0+ required",
            }

        # Test model loading
        try:
            nlp = spacy.load("en_core_web_md")
            _ = nlp("Test sentence for NER validation.")  # Validate model is functional
            return {
                "status": "✅",
                "version": version,
                "model": "en_core_web_md",
                "detail": f"spaCy {version} + model loaded successfully",
            }
        except OSError:
            return {
                "status": "⚠️",
                "version": version,
                "detail": "spaCy installed but model not found. Run: python -m spacy download en_core_web_md",
            }
    except ImportError:
        return {
            "status": "❌",
            "version": "not installed",
            "detail": "spaCy not found. Run: uv sync",
        }


def validate_markitdown() -> Dict[str, Any]:
    """Validate MarkItDown installation (optional but recommended)."""
    try:
        import markitdown

        return {
            "status": "✅",
            "version": getattr(markitdown, "__version__", "unknown"),
            "detail": "MarkItDown available for HTML cleaning",
        }
    except ImportError:
        return {
            "status": "⚠️",
            "fallback": "BeautifulSoup",
            "detail": "MarkItDown not found. Fallback to BeautifulSoup (slower, 3-5x). Install: uv pip install markitdown",
        }


def validate_beautifulsoup() -> Dict[str, Any]:
    """Validate BeautifulSoup installation."""
    try:
        import bs4

        return {"status": "✅", "version": bs4.__version__, "detail": "BeautifulSoup4 available"}
    except ImportError:
        return {"status": "❌", "detail": "BeautifulSoup4 not found. Run: uv sync"}


def validate_lxml() -> Dict[str, Any]:
    """Validate lxml installation (optional but recommended for speed)."""
    try:
        import lxml  # noqa: F401

        return {"status": "✅", "detail": "lxml available (fast C-based parser)"}
    except ImportError:
        return {
            "status": "⚠️",
            "fallback": "html.parser",
            "detail": "lxml not found. Fallback to html.parser (pure Python, slower). See system dependencies below.",
        }


def validate_tiktoken() -> Dict[str, Any]:
    """Validate tiktoken for token counting."""
    try:
        import tiktoken

        enc = tiktoken.encoding_for_model("gpt-4")
        test_text = "Test token counting for Claude API cost estimation."
        tokens = len(enc.encode(test_text))
        return {"status": "✅", "detail": f"tiktoken working (test: {tokens} tokens)"}
    except Exception as e:
        return {"status": "❌", "detail": f"tiktoken error: {str(e)}"}


def validate_pydantic() -> Dict[str, Any]:
    """Validate Pydantic v2 (required for spaCy 3.8+)."""
    try:
        import pydantic

        major_version = int(pydantic.__version__.split(".")[0])
        if major_version >= 2:
            return {
                "status": "✅",
                "version": pydantic.__version__,
                "detail": f"Pydantic {pydantic.__version__} (v2+ required for spaCy)",
            }
        else:
            return {
                "status": "❌",
                "version": pydantic.__version__,
                "detail": f"Pydantic {pydantic.__version__} found, but v2+ required",
            }
    except ImportError:
        return {"status": "❌", "detail": "Pydantic not found. Run: uv sync"}


def check_system_dependencies() -> Dict[str, Any]:
    """Check for system-level dependencies (lxml, libxml2, etc.)."""
    os_name = platform.system()
    results: Dict[str, Any] = {"platform": os_name, "checks": {}}
    checks_dict: Dict[str, str] = results["checks"]

    if os_name == "Linux":
        print(f"\n{BOLD}System Dependencies (Linux):{RESET}")
        libs = ["libxml2", "libxslt", "python3-dev"]
        for lib in libs:
            try:
                result = subprocess.run(["dpkg", "-l"], capture_output=True, text=True, timeout=5)
                if lib in result.stdout:
                    print_status("✅", lib, "installed via apt")
                    checks_dict[lib] = "✅"
                else:
                    print_status("⚠️", lib, "not found")
                    checks_dict[lib] = "⚠️"
            except Exception:
                print_status("⚠️", lib, "check unavailable")
                checks_dict[lib] = "⚠️"

        print_status(
            "ℹ️", "Install missing", "sudo apt-get install libxml2-dev libxslt-dev python3-dev"
        )

    elif os_name == "Darwin":  # macOS
        print(f"\n{BOLD}System Dependencies (macOS):{RESET}")
        libs = ["libxml2", "libxslt"]
        for lib in libs:
            try:
                result = subprocess.run(
                    ["brew", "list", lib], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    print_status("✅", lib, "installed via Homebrew")
                    checks_dict[lib] = "✅"
                else:
                    print_status("⚠️", lib, "not found")
                    checks_dict[lib] = "⚠️"
            except Exception:
                print_status("⚠️", lib, "check unavailable")
                checks_dict[lib] = "⚠️"

        print_status("ℹ️", "Install missing", "brew install libxml2 libxslt")

    elif os_name == "Windows":
        print(f"\n{BOLD}System Dependencies (Windows):{RESET}")
        print_status("✅", "windows_wheels", "C libraries auto-installed via pip wheels")
        checks_dict["windows_wheels"] = "✅"

    return results


def main() -> int:
    """Run full validation suite."""
    print(f"\n{BOLD}{'='*70}{RESET}")
    print(f"{BOLD}🔍 NLP Setup Validation for Issue #7{RESET}")
    print(f"{BOLD}{'='*70}{RESET}\n")

    # Core validations
    print(f"{BOLD}Python & Core Dependencies:{RESET}")
    py_result = validate_python_version()
    print_status(py_result["status"], "Python", py_result["detail"])

    sp_result = validate_spacy()
    print_status(sp_result["status"], "spaCy", sp_result.get("detail", ""))

    pd_result = validate_pydantic()
    print_status(pd_result["status"], "Pydantic", pd_result["detail"])

    tk_result = validate_tiktoken()
    print_status(tk_result["status"], "tiktoken", tk_result["detail"])

    # HTML processing chain
    print(f"\n{BOLD}HTML Processing Chain:{RESET}")
    md_result = validate_markitdown()
    print_status(md_result["status"], "MarkItDown", md_result.get("detail", ""))

    bs_result = validate_beautifulsoup()
    print_status(bs_result["status"], "BeautifulSoup", bs_result["detail"])

    lx_result = validate_lxml()
    print_status(lx_result["status"], "lxml", lx_result.get("detail", ""))

    # System dependencies
    check_system_dependencies()

    # Summary
    print(f"\n{BOLD}{'='*70}{RESET}")
    critical_ok = (
        py_result["status"] == "✅"
        and sp_result["status"] == "✅"
        and pd_result["status"] == "✅"
        and tk_result["status"] == "✅"
    )

    if critical_ok:
        print(f"{GREEN}{BOLD}✅ ALL CRITICAL COMPONENTS OK{RESET}")
        print("\nReady for NLP pipeline! Optional optimizations:")
        if md_result["status"] == "⚠️":
            print("  • Install MarkItDown: uv pip install markitdown")
        if lx_result["status"] == "⚠️":
            print("  • Install lxml: check system dependencies above")
        print(f"{BOLD}{'='*70}{RESET}\n")
        return 0
    else:
        print(f"{RED}{BOLD}❌ CRITICAL ISSUES FOUND{RESET}")
        if py_result["status"] == "❌":
            print(f"  • {py_result['detail']}")
        if sp_result["status"] == "❌":
            print(f"  • {sp_result['detail']}")
        if pd_result["status"] == "❌":
            print(f"  • {pd_result['detail']}")
        if tk_result["status"] == "❌":
            print(f"  • {tk_result['detail']}")
        print(f"{BOLD}{'='*70}{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
