import os
import socket
import subprocess
import sys
import time
import webbrowser


def wait_for_port(port, timeout=90):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection(("localhost", port), timeout=1):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            time.sleep(1)
    return False


def is_port_open(port):
    try:
        with socket.create_connection(("localhost", port), timeout=1):
            return True
    except OSError:
        return False


def resolve_runtime():
    if getattr(sys, "frozen", False):
        project_root = os.path.dirname(sys.executable)
        python_exe = r"C:\Users\amg30\.conda\envs\torch_win\python.exe"
    else:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        python_exe = sys.executable

    os.chdir(project_root)
    return project_root, python_exe


def stop_process(process):
    if process is None or process.poll() is not None:
        return
    process.terminate()
    time.sleep(1)
    if process.poll() is None:
        process.kill()


def main():
    print("=" * 64)
    print("        Smart Assembly Line - Dashboard Control Station")
    print("=" * 64)

    project_root, python_exe = resolve_runtime()
    print(f"[STARTUP] Project root: {project_root}")
    print(f"[STARTUP] Python environment: {python_exe}")

    print("[STARTUP] Verifying Docker Desktop is running...")
    try:
        subprocess.run(
            ["docker", "info"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("\nERROR: Docker is not running or not installed.")
        print("Open Docker Desktop, then start this dashboard launcher again.\n")
        input("Press Enter to exit...")
        sys.exit(1)

    compose_file = os.path.join("deployment", "docker-compose.local.yml")
    print("[STARTUP] Starting PostgreSQL and Mosquitto MQTT...")
    try:
        subprocess.run(["docker", "compose", "-f", compose_file, "up", "-d"], check=True)
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] Failed to start Docker Compose: {exc}")
        input("Press Enter to exit...")
        sys.exit(1)

    print("[STARTUP] Waiting for PostgreSQL on port 5433...")
    if not wait_for_port(5433, timeout=90):
        print("[ERROR] PostgreSQL did not become ready.")
        input("Press Enter to exit...")
        sys.exit(1)

    print("[STARTUP] Waiting for Mosquitto MQTT on port 1883...")
    if not wait_for_port(1883, timeout=30):
        print("[ERROR] Mosquitto did not become ready.")
        input("Press Enter to exit...")
        sys.exit(1)

    print("[STARTUP] Applying database migrations...")
    try:
        subprocess.run([python_exe, "-m", "alembic", "upgrade", "head"], check=True)
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] Alembic migrations failed: {exc}")
        input("Press Enter to exit...")
        sys.exit(1)

    log_dir = os.path.join("data", "runtime", "logs")
    os.makedirs(log_dir, exist_ok=True)

    logger_proc = None
    dashboard_proc = None
    logger_log = open(os.path.join(log_dir, "logger.log"), "w", encoding="utf-8")
    logger_err = open(os.path.join(log_dir, "logger.err.log"), "w", encoding="utf-8")
    dashboard_log = open(os.path.join(log_dir, "dashboard.log"), "w", encoding="utf-8")
    dashboard_err = open(os.path.join(log_dir, "dashboard.err.log"), "w", encoding="utf-8")

    try:
        print("[STARTUP] Launching logger service...")
        logger_proc = subprocess.Popen(
            [python_exe, "-u", "src/utils/logger.py"],
            stdout=logger_log,
            stderr=logger_err,
        )

        if is_port_open(8000):
            print("[STARTUP] Dashboard port 8000 is already open; using existing dashboard.")
        else:
            print("[STARTUP] Launching dashboard backend...")
            dashboard_proc = subprocess.Popen(
                [
                    python_exe,
                    "-u",
                    "-m",
                    "uvicorn",
                    "src.dashboard.main:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8000",
                ],
                stdout=dashboard_log,
                stderr=dashboard_err,
            )

        time.sleep(2)
        if logger_proc.poll() is not None:
            print("[ERROR] Logger exited. Check data/runtime/logs/logger.err.log")
            sys.exit(1)
        if dashboard_proc is not None and dashboard_proc.poll() is not None:
            print("[ERROR] Dashboard exited. Check data/runtime/logs/dashboard.err.log")
            sys.exit(1)

        print("[STARTUP] Opening dashboard: http://localhost:8000")
        webbrowser.open("http://localhost:8000")

        print("\n" + "=" * 64)
        print("   Dashboard is independent from the camera/video process.")
        print("   Use Turn On Project in the dashboard to start detection.")
        print("   Pressing q in the camera window only stops detection.")
        print("   Press Enter here only when you want to shut down the dashboard station.")
        print("=" * 64 + "\n")
        input()
    except (KeyboardInterrupt, EOFError):
        print("\n[SHUTDOWN] Stopping dashboard station...")
    finally:
        stop_process(logger_proc)
        stop_process(dashboard_proc)

        logger_log.close()
        logger_err.close()
        dashboard_log.close()
        dashboard_err.close()

        print("[SHUTDOWN] Stopping Docker Compose services...")
        try:
            subprocess.run(["docker", "compose", "-f", compose_file, "down"], check=True)
        except subprocess.CalledProcessError as exc:
            print(f"[WARNING] Failed to stop Docker Compose cleanly: {exc}")

        print("[SHUTDOWN] Dashboard station closed.")


if __name__ == "__main__":
    main()
