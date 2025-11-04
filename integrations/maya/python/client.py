"""
Maya client for solar analysis server using urllib (Maya-safe)
Non-blocking with worker threads and Maya scriptJob polling
"""

import urllib.request
import urllib.parse
import json
import os
import threading
from maya import cmds


class SolarAnalysisClient:
    """
    Client for communicating with solar analysis server
    Handles job submission, polling, and result retrieval
    All network operations happen in background threads
    """

    def __init__(
        self, server_url="http://localhost:8000", timeout=30.0, status_callback=None
    ):
        self.server_url = server_url
        self.timeout = timeout
        self.current_job_id = None
        self.timer_id = None
        self.result_callback = None
        self.status_callback = status_callback  # NEW: For progress updates
        self.worker_thread = None

    def _http_post_multipart(self, url, files_dict):
        """
        POST multipart/form-data using urllib

        Args:
            url: Full URL to POST to
            files_dict: Dict of {field_name: (filename, file_bytes, content_type)}

        Returns:
            Response JSON dict
        """
        boundary = "----WebKitFormBoundary" + os.urandom(16).hex()

        # Build multipart body
        body = []
        for field_name, (filename, file_bytes, content_type) in files_dict.items():
            body.append(f"--{boundary}".encode())
            body.append(
                f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"'.encode()
            )
            body.append(f"Content-Type: {content_type}".encode())
            body.append(b"")
            body.append(file_bytes)

        body.append(f"--{boundary}--".encode())
        body.append(b"")

        body_bytes = b"\r\n".join(body)

        # Create request
        req = urllib.request.Request(
            url,
            data=body_bytes,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body_bytes)),
            },
        )

        # Send request
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode())

    def _http_get_json(self, url):
        """GET request returning JSON"""
        with urllib.request.urlopen(url, timeout=self.timeout) as response:
            return json.loads(response.read().decode())

    def _http_get_bytes(self, url):
        """GET request returning raw bytes"""
        with urllib.request.urlopen(url, timeout=self.timeout) as response:
            return response.read()

    def submit_job(self, usd_path, epw_path, callback=None):
        """
        Submit analysis job to server (non-blocking)

        Args:
            usd_path: Path to USD scene file
            epw_path: Path to EPW weather file
            callback: Function to call when complete, receives (success, result_path_or_error)
        """
        self.result_callback = callback

        # Start worker thread to handle submission
        def worker():
            try:
                print("Submitting job to server...")

                # Read files
                with open(usd_path, "rb") as f:
                    usd_bytes = f.read()
                with open(epw_path, "rb") as f:
                    epw_bytes = f.read()

                # Prepare multipart data
                files_dict = {
                    "usd_file": ("scene.usda", usd_bytes, "application/octet-stream"),
                    "epw_file": ("weather.epw", epw_bytes, "application/octet-stream"),
                }

                # Submit (happens in worker thread)
                url = f"{self.server_url}/submit"
                data = self._http_post_multipart(url, files_dict)

                self.current_job_id = data["job_id"]

                print(f"Job submitted!")
                print(f"   Job ID: {self.current_job_id}")
                print(f"   Status: {data['status']}")

                # Start polling (back in main thread)
                cmds.evalDeferred(lambda: self.start_polling())

            except Exception as e:
                error_msg = str(e)
                print(f"Error submitting job: {error_msg}")

                # FIX: Capture variables as default arguments
                callback = self.result_callback
                if callback:
                    cmds.evalDeferred(lambda msg=error_msg, cb=callback: cb(False, msg))

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()

    def check_status(self):
        """
        Check job status (called by Maya timer)
        Returns True to continue polling, False to stop
        """
        if not self.current_job_id:
            return False

        # Use worker thread for network call
        def worker():
            try:
                url = f"{self.server_url}/status/{self.current_job_id}"
                status_data = self._http_get_json(url)
                status = status_data["status"]

                if status == "queued":
                    print("⏳ Job queued...")
                    # NEW: Send status update to UI
                    if self.status_callback:
                        cb = self.status_callback
                        cmds.evalDeferred(lambda callback=cb: callback("queued", 0))

                elif status == "processing":
                    print("Processing...")
                    # NEW: Send status update to UI (50% progress for processing)
                    if self.status_callback:
                        cb = self.status_callback
                        cmds.evalDeferred(
                            lambda callback=cb: callback("processing", 50)
                        )

                elif status == "complete":
                    print("Analysis complete! Downloading results...")
                    # NEW: Send status update to UI
                    if self.status_callback:
                        cb = self.status_callback
                        cmds.evalDeferred(
                            lambda callback=cb: callback("downloading", 75)
                        )

                    # Download in worker thread, then stop polling
                    self.download_result()
                    return False  # Stop polling

                elif status == "error":
                    error_msg = status_data.get("error", "Unknown error")
                    print(f"Analysis failed: {error_msg}")

                    # NEW: Send error to UI
                    if self.status_callback:
                        cb = self.status_callback
                        cmds.evalDeferred(
                            lambda callback=cb, msg=error_msg: callback("error", 0, msg)
                        )

                    # FIX: Capture variables as default arguments
                    callback = self.result_callback
                    if callback:
                        cmds.evalDeferred(
                            lambda msg=error_msg, cb=callback: cb(False, msg)
                        )

                    return False  # Stop polling

                # Continue polling
                cmds.evalDeferred(lambda: self._schedule_next_poll())

            except Exception as e:
                print(f"Error checking status: {e}")
                # Keep trying
                cmds.evalDeferred(lambda: self._schedule_next_poll())

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        return True

    def _schedule_next_poll(self):
        """Schedule next status check in 2 seconds"""
        cmds.scriptJob(runOnce=True, event=["idle", lambda: self.check_status()])

    def download_result(self):
        """Download completed result file (runs in worker thread)"""

        def worker():
            try:
                url = f"{self.server_url}/result/{self.current_job_id}"
                result_bytes = self._http_get_bytes(url)

                # Save result to temp location - use workspace instead of temp dir
                result_dir = cmds.workspace(query=True, rootDirectory=True)
                if not result_dir:
                    # Fallback to temp dir if workspace not set
                    result_dir = cmds.internalVar(userTmpDir=True)

                result_filename = f"solar_result_{self.current_job_id}.usda"
                result_path = os.path.join(result_dir, result_filename)

                # Ensure we have write permissions
                if os.path.exists(result_path):
                    try:
                        os.remove(result_path)
                    except:
                        # If can't remove, use temp dir with timestamp
                        import time

                        result_filename = f"solar_result_{int(time.time())}.usda"
                        result_path = os.path.join(
                            cmds.internalVar(userTmpDir=True), result_filename
                        )

                with open(result_path, "wb") as f:
                    f.write(result_bytes)

                print(f"Results saved to: {result_path}")

                # NEW: Send completion update to UI
                if self.status_callback:
                    cb = self.status_callback
                    cmds.evalDeferred(lambda callback=cb: callback("complete", 100))

                # FIX: Capture variables as default arguments
                callback = self.result_callback
                if callback:
                    cmds.evalDeferred(
                        lambda path=result_path, cb=callback: cb(True, path)
                    )

            except Exception as e:
                error_msg = str(e)
                print(f"Error downloading result: {error_msg}")

                # FIX: Capture variables as default arguments
                callback = self.result_callback
                if callback:
                    cmds.evalDeferred(lambda msg=error_msg, cb=callback: cb(False, msg))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def start_polling(self):
        """Start Maya scriptJob to poll status"""
        if self.timer_id is not None:
            self.stop_polling()

        print("Started polling for status updates...")
        self.check_status()

    def stop_polling(self):
        """Stop polling (cleanup)"""
        if self.timer_id:
            try:
                cmds.scriptJob(kill=self.timer_id, force=True)
            except:
                pass
            self.timer_id = None

        self.current_job_id = None
        self.result_callback = None

    def get_server_status(self):
        """
        Check if server is running and get queue stats
        This is a blocking call, use only for initial setup
        """
        try:
            url = self.server_url
            return self._http_get_json(url)
        except:
            return None


if __name__ == "__main__":
    # For testing outside Maya
    print("This module is designed to run inside Maya")
    print("Import and use SolarAnalysisClient class")
