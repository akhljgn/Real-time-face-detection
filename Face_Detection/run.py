import sys
import threading
import webbrowser
from server.flask_app import run_flask, set_worker

def main():
    # 1. Start ML worker in background
    from ml.worker import RecognitionWorker
    worker = RecognitionWorker()
    set_worker(worker)
    worker.start()
    print("[APP] Recognition worker started")

    # 2. Open browser automatically
    threading.Timer(2.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()

    # 3. Run Flask (blocking)
    print("[APP] Starting Flask on http://127.0.0.1:5000")
    run_flask()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[APP] Shutting down...")