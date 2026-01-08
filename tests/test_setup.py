# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Usage:
This file defines tasks for building Protos, webhost and extensions

To use these tasks, you can run the following commands:

1. Set up the Mock Server for Extension Bundles:
    invoke -c test_setup mock-extension-site
2. Set up the Azure Functions Core Tools webhost:
   invoke -c test_setup webhost

"""
import os
import pathlib
import shutil
import sys
import json
import re
import tempfile
import zipfile
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler

from invoke import task

ROOT_DIR = pathlib.Path(__file__).parent
ARTIFACTS_DIR = ROOT_DIR / "artifacts"
BUILD_DIR = ROOT_DIR / "build"

def extract_core_tools(src_zip, dest_folder):
    """Extracts Azure Functions Core Tools to the specified folder."""
    print(f"Extracting Core Tools from {src_zip}")

    if dest_folder.exists():
        shutil.rmtree(dest_folder)
    os.makedirs(dest_folder, exist_ok=True)

    with zipfile.ZipFile(src_zip, "r") as archive:
        archive.extractall(dest_folder)
    # Make func executable on Unix systems
    system = sys.platform.lower()
    if not system.startswith("win"):
        func_path = dest_folder / "func"
        if func_path.exists():
            os.chmod(func_path, 0o755)

    print(f"Azure Functions Core Tools extracted to {dest_folder}")
    return dest_folder


@task
def webhost(
    c,
    clean=False,
    webhost_dir=None
):
    """Builds the webhost"""

    if webhost_dir is None:
        webhost_dir = BUILD_DIR / "webhost"
    else:
        webhost_dir = pathlib.Path(webhost_dir)

    if clean:
        print("Deleting webhost dir")
        shutil.rmtree(webhost_dir, ignore_errors=True)
        print("Deleted webhost dir")
        return

    # Find the core tools zip file
    repo_root = ROOT_DIR.parent
    core_tools_dir = repo_root / "core-tools"

    # Find the zip file
    zip_files = list(core_tools_dir.glob("*.zip"))
    if not zip_files:
        raise FileNotFoundError(f"No zip files found in {core_tools_dir}")

    # Use the first (or most recent) zip file
    zip_path = zip_files[0]
    print(f"Using Core Tools zip: {zip_path}")

    create_webhost_folder(webhost_dir)
    extract_core_tools(zip_path, webhost_dir)


def create_webhost_folder(dest_folder):
    if dest_folder.exists():
        shutil.rmtree(dest_folder)
    os.makedirs(dest_folder, exist_ok=True)
    print(f"Functions Host folder is created in {dest_folder}")


@task
def clean(c):
    """Clean build directory."""

    print("Deleting build directory")
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    print("Deleted build directory")


def _extract_version_from_filename(filename):
    """Extract version number from extension bundle filename."""
    # Pattern for regular bundle: Microsoft.Azure.Functions.ExtensionBundle.4.24.1_any-any.zip
    # Pattern for preview bundle: Microsoft.Azure.Functions.ExtensionBundle.Preview.4.25.1_win-any.zip

    # Try preview pattern first
    preview_pattern = r"Microsoft\.Azure\.Functions\.ExtensionBundle\.Preview\.(\d+\.\d+\.\d+)_.*\.zip"
    match = re.match(preview_pattern, filename)
    if match:
        return match.group(1)

    # Try regular pattern
    regular_pattern = (
        r"Microsoft\.Azure\.Functions\.ExtensionBundle\.(\d+\.\d+\.\d+)_.*\.zip"
    )
    match = re.match(regular_pattern, filename)
    if match:
        return match.group(1)

    return None


def _is_preview_bundle(filename):
    """Check if the filename is a preview bundle."""
    return "Preview" in filename


def _get_bundle_id(filename):
    """Get the bundle ID from filename."""
    if _is_preview_bundle(filename):
        return "Microsoft.Azure.Functions.ExtensionBundle.Preview"
    else:
        return "Microsoft.Azure.Functions.ExtensionBundle"


def _setup_extension_bundle_structure(temp_dir, artifacts_dir):
    """Set up the ExtensionBundle directory structure and copy files."""
    print(f"Setting up ExtensionBundle structure in {temp_dir}")

    # Create the directory structure
    extension_bundles_dir = temp_dir / "ExtensionBundles"
    extension_bundles_dir.mkdir(parents=True, exist_ok=True)

    # Find all ExtensionBundle zip files (both regular and preview)
    artifacts_path = pathlib.Path(artifacts_dir)
    bundle_files = list(
        artifacts_path.glob("Microsoft.Azure.Functions.ExtensionBundle*.zip")
    )

    if not bundle_files:
        print("No ExtensionBundle files found in artifacts directory", file=sys.stderr)
        return None

    # Group files by bundle type and version
    bundle_groups = {
        "Microsoft.Azure.Functions.ExtensionBundle": {},
        "Microsoft.Azure.Functions.ExtensionBundle.Preview": {},
    }

    for file_path in bundle_files:
        version = _extract_version_from_filename(file_path.name)
        bundle_id = _get_bundle_id(file_path.name)

        if version and bundle_id in bundle_groups:
            if version not in bundle_groups[bundle_id]:
                bundle_groups[bundle_id][version] = []
            bundle_groups[bundle_id][version].append(file_path)

    # Create directory structure and copy files for each bundle type
    created_bundles = {}
    for bundle_id, versions in bundle_groups.items():
        if not versions:
            continue

        print(f"Found {bundle_id} versions: {list(versions.keys())}")

        # Create bundle directory
        bundle_dir = extension_bundles_dir / bundle_id
        bundle_dir.mkdir(exist_ok=True)

        # Create version directories and copy files
        for version, files in versions.items():
            version_dir = bundle_dir / version
            version_dir.mkdir(exist_ok=True)

            for file_path in files:
                dest_path = version_dir / file_path.name
                print(f"Copying {file_path.name} to {dest_path}")
                shutil.copy2(file_path, dest_path)

        # Create index.json with all versions for this bundle
        index_content = sorted(versions.keys())
        index_path = bundle_dir / "index.json"
        with open(index_path, "w") as f:
            json.dump(index_content, f, indent=2)

        print(f"Created index.json for {bundle_id} with versions: {index_content}")
        created_bundles[bundle_id] = index_content

    if not created_bundles:
        print("No valid ExtensionBundle versions found", file=sys.stderr)
        return None

    return temp_dir


class ExtensionBundleHTTPHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for serving ExtensionBundle files."""

    def __init__(self, *args, directory=None, **kwargs):
        self.directory = directory
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        """Log an arbitrary message."""
        print(f"[MockServer] {self.address_string()} - {format % args}")


def _start_mock_server(temp_dir, port=3000):
    """Start a mock HTTP server to serve ExtensionBundle files."""
    print(f"Starting mock server on port {port} serving {temp_dir}")

    # Create a custom handler bound to the temp directory
    def handler_factory(*args, **kwargs):
        return ExtensionBundleHTTPHandler(*args, directory=str(temp_dir), **kwargs)

    # Start server
    try:
        server = HTTPServer(("localhost", port), handler_factory)
        print(f"Mock ExtensionBundle server running at http://localhost:{port}")
        print(
            f"Index URL: http://localhost:{port}/ExtensionBundles/Microsoft.Azure.Functions.ExtensionBundle/index.json"
        )

        # Start server in a separate thread
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        return server, server_thread
    except OSError as e:
        if e.errno == 10048:  # Port already in use
            print(f"Port {port} is already in use. Trying port {port + 1}")
            return _start_mock_server(temp_dir, port + 1)
        else:
            raise


@task
def mock_extension_site(c, port=3000, artifacts_dir=None, keep_alive=False):
    """Start a mock site for downloading ExtensionBundle packages.

    Args:
        port: Port to run the mock server on (default: 3000)
        artifacts_dir: Directory containing ExtensionBundle artifacts (default: ../artifacts)
        keep_alive: Keep the server running indefinitely (default: False for testing)
    """

    if artifacts_dir is None:
        artifacts_dir = ROOT_DIR.parent / "artifacts"
    else:
        artifacts_dir = pathlib.Path(artifacts_dir)

    if not artifacts_dir.exists():
        print(f"Artifacts directory not found: {artifacts_dir}", file=sys.stderr)
        sys.exit(1)

    # Create temporary directory
    temp_dir = pathlib.Path(tempfile.mkdtemp(prefix="extension_bundle_mock_"))
    print(f"Created temporary directory: {temp_dir}")

    try:
        # Setup directory structure and copy files
        mock_dir = _setup_extension_bundle_structure(temp_dir, artifacts_dir)
        if not mock_dir:
            print("Failed to setup ExtensionBundle structure", file=sys.stderr)
            sys.exit(1)
        # Start mock server
        server, server_thread = _start_mock_server(mock_dir, port)

        print("\n" + "=" * 70)
        print("Mock ExtensionBundle site is ready!")
        print("=" * 70)
        print(f"Base URL: http://localhost:{server.server_port}")

        # Show index URLs and example download URLs for both bundle types
        bundle_types = [
            "Microsoft.Azure.Functions.ExtensionBundle",
            "Microsoft.Azure.Functions.ExtensionBundle.Preview",
        ]

        for bundle_id in bundle_types:
            bundle_dir = mock_dir / "ExtensionBundles" / bundle_id
            index_file = bundle_dir / "index.json"

            if index_file.exists():
                print(f"\n{bundle_id}:")
                print(
                    f"  Index URL: http://localhost:{server.server_port}/ExtensionBundles/{bundle_id}/index.json"
                )

                with open(index_file, "r") as f:
                    versions = json.load(f)

                print(f"  Available versions: {versions}")
                print("  Example download URLs:")

                for version in versions[:2]:  # Show first 2 versions as examples
                    version_dir = bundle_dir / version
                    if version_dir.exists():
                        zip_files = list(version_dir.glob("*.zip"))
                        for zip_file in zip_files[:2]:  # Show first 2 files per version
                            print(
                                f"    http://localhost:{server.server_port}/ExtensionBundles/{bundle_id}/{version}/{zip_file.name}"
                            )

        print("=" * 70)

        if keep_alive:
            print("\nServer is running. Press Ctrl+C to stop...")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down server...")
        else:
            print(
                "\nServer started in background. Use Ctrl+C to stop when done testing."
            )
            print("For testing purposes, the server will run until interrupted.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down server...")

    finally:
        # Cleanup
        if "server" in locals():
            server.shutdown()
            server.server_close()

        # Clean up temporary directory
        print(f"Cleaning up temporary directory: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)
