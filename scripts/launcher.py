# scripts/launcher.py

import os
import sys
import time
import socket
import subprocess
import webbrowser

def wait_for_port(port, timeout=90):
    """Wait until a local port is open and accepting TCP connections."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection(("localhost", port), timeout=1):
                return True
        except (socket.timeout, ConnectionRefusedError):
            time.sleep(1)
    return False


def wait_for_port_to_close(port, timeout=20):
    """Wait until a local port stops accepting TCP connections."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection(("localhost", port), timeout=1):
                time.sleep(1)
        except OSError:
            return True
    return False


def close_dashboard_exe_if_running():
    """
    If the standalone dashboard station is open, close it before the full
    assembly launcher starts its own dashboard/backend services.
    """
    if os.name != "nt":
        return

    current_exe = os.path.basename(sys.executable).lower()
    if current_exe == "smartassemblydashboard.exe":
        return

    print("[STARTUP] Checking for standalone dashboard station...")
    result = subprocess.run(
        ["taskkill", "/IM", "SmartAssemblyDashboard.exe", "/T", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode == 0:
        print("[STARTUP] Closed SmartAssemblyDashboard.exe before full launch.")
        if not wait_for_port_to_close(8000, timeout=20):
            print("[WARNING] Dashboard port 8000 is still busy after closing the dashboard exe.")


def main():
    print("=" * 60)
    print("        Smart Assembly Line - Auto Launcher")
    print("=" * 60)

    # 1. Resolve Python path
    if getattr(sys, 'frozen', False):
        # Running as compiled binary
        python_exe = r"C:\Users\amg30\.conda\envs\torch_win\python.exe"
        # We need to set working directory to the directory containing the exe
        exe_dir = os.path.dirname(sys.executable)
        os.chdir(exe_dir)
        print(f"[STARTUP] Running from binary, setting working directory to: {exe_dir}")
    else:
        # Running as raw script
        python_exe = sys.executable
        # Set working directory to project root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        os.chdir(project_root)
        print(f"[STARTUP] Running from source, setting working directory to: {project_root}")

    print(f"[STARTUP] Using Python environment: {python_exe}")
    close_dashboard_exe_if_running()

    # 2. Check if Docker is running
    print("[STARTUP] Verifying Docker Desktop is running...")
    try:
        subprocess.run(
            ["docker", "info"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("\n" + "!" * 60)
        print("  ERROR: Docker is not running or not installed.")
        print("  Please open Docker Desktop and try launching again.")
        print("!" * 60 + "\n")
        input("Press Enter to exit...")
        sys.exit(1)

    # 3. Start Docker Compose infrastructure
    print("[STARTUP] Starting PostgreSQL and Mosquitto MQTT via Docker Compose...")
    compose_file = os.path.join("deployment", "docker-compose.local.yml")
    try:
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "up", "-d"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to start Docker Compose: {e}")
        input("Press Enter to exit...")
        sys.exit(1)

    # 4. Wait for ports
    print("[STARTUP] Waiting for PostgreSQL (port 5433) to accept connections...")
    if not wait_for_port(5433, 90):
        print("[ERROR] PostgreSQL database failed to start or configure.")
        input("Press Enter to exit...")
        sys.exit(1)

    print("[STARTUP] Waiting for Mosquitto MQTT broker (port 1883)...")
    if not wait_for_port(1883, 30):
        print("[ERROR] Mosquitto MQTT broker failed to start.")
        input("Press Enter to exit...")
        sys.exit(1)

    # 5. Apply Database Migrations
    print("[STARTUP] Applying database migrations (alembic)...")
    try:
        subprocess.run(
            [python_exe, "-m", "alembic", "upgrade", "head"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Alembic migrations failed: {e}")
        input("Press Enter to exit...")
        sys.exit(1)

    # 6. Launch Background Services
    print("[STARTUP] Checking if Dashboard port (8000) is free...")
    s_test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s_test.bind(("127.0.0.1", 8000))
        s_test.close()
    except OSError:
        print("\n" + "!" * 60)
        print("  ERROR: Port 8000 is already in use by another process.")
        print("  Please close any other dashboard instances or programs running")
        print("  on port 8000, then try again.")
        print("!" * 60 + "\n")
        
        # Stop Docker Compose since we started it
        print("[SHUTDOWN] Stopping Docker Compose services...")
        try:
            subprocess.run(["docker", "compose", "-f", compose_file, "down"], check=True)
        except Exception:
            pass
            
        input("Press Enter to exit...")
        sys.exit(1)

    log_dir = os.path.join("data", "runtime", "logs")
    os.makedirs(log_dir, exist_ok=True)

    logger_log = open(os.path.join(log_dir, "logger.log"), "w", encoding="utf-8")
    logger_err = open(os.path.join(log_dir, "logger.err.log"), "w", encoding="utf-8")
    dashboard_log = open(os.path.join(log_dir, "dashboard.log"), "w", encoding="utf-8")
    dashboard_err = open(os.path.join(log_dir, "dashboard.err.log"), "w", encoding="utf-8")

    logger_proc = None
    dashboard_proc = None

    try:
        print("[STARTUP] Launching Logger background service...")
        logger_proc = subprocess.Popen(
            [python_exe, "-u", "src/utils/logger.py"],
            stdout=logger_log,
            stderr=logger_err
        )

        print("[STARTUP] Launching Dashboard backend (FastAPI)...")
        dashboard_proc = subprocess.Popen(
            [python_exe, "-u", "-m", "uvicorn", "src.dashboard.main:app", "--host", "0.0.0.0", "--port", "8000"],
            stdout=dashboard_log,
            stderr=dashboard_err
        )

        # Allow services to initialize
        time.sleep(2)
        if logger_proc.poll() is not None:
            print("[ERROR] Logger service failed to stay running. Check data/runtime/logs/logger.err.log")
            sys.exit(1)
        if dashboard_proc.poll() is not None:
            print("[ERROR] Dashboard service failed to stay running. Check data/runtime/logs/dashboard.err.log")
            sys.exit(1)

        # 7. Open Dashboard in Browser
        print("[STARTUP] Opening dashboard in browser: http://localhost:8000")
        webbrowser.open("http://localhost:8000")

        auto_pipeline = "--no-pipeline" not in sys.argv

        if auto_pipeline:
            # 8. Start Vision Pipeline
            print("[PIPELINE] Starting vision tracking pipeline window...")
            print("=" * 60)
            print("   TO QUIT: Press 'q' in the Production Tracker window,")
            print("            or close the CV2 window, or press Ctrl+C in this console.")
            print("   Dashboard, logger, and Docker will stay up after the pipeline exits.")
            print("=" * 60)

            try:
                subprocess.run([python_exe, "scripts/run_pipeline.py"], check=True)
            except KeyboardInterrupt:
                print("\n[SHUTDOWN] Interrupted by user via console.")
            except subprocess.CalledProcessError as e:
                print(f"\n[PIPELINE] Exited with code {e.returncode}.")

        print("\n" + "=" * 60)
        print("   [STARTUP] Control dashboard is running at http://localhost:8000")
        if auto_pipeline:
            print("   [STARTUP] The vision pipeline was started automatically.")
        else:
            print("   [STARTUP] Use the dashboard Turn On Project button to start detection.")
        print("   [STARTUP] Use Turn Off Project to stop detection and send serial off.")
        print("   [STARTUP] Press Enter in this window to shut down background services...")
        print("=" * 60 + "\n")
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            print("\n[SHUTDOWN] Shutting down launcher...")
    finally:
        print("[SHUTDOWN] Shutting down background services...")
        # Terminate processes
        if logger_proc is not None and logger_proc.poll() is None:
            logger_proc.terminate()
        if dashboard_proc is not None and dashboard_proc.poll() is None:
            dashboard_proc.terminate()
        
        time.sleep(1)
        if logger_proc is not None and logger_proc.poll() is None:
            logger_proc.kill()
        if dashboard_proc is not None and dashboard_proc.poll() is None:
            dashboard_proc.kill()

        logger_log.close()
        logger_err.close()
        dashboard_log.close()
        dashboard_err.close()

        # Stop Docker Compose
        print("[SHUTDOWN] Stopping Docker Compose services...")
        try:
            subprocess.run(
                ["docker", "compose", "-f", compose_file, "down"],
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to stop Docker Compose: {e}")

        print("[SHUTDOWN] Clean exit. Goodbye!")

if __name__ == "__main__":
    main()
