from flask import Flask, request, render_template, Response, stream_with_context
import psycopg2, queue, time

app = Flask(__name__)
clients = []

DB_CONFIG = {
    "dbname": "demo1",
    "user": "scanuser",
    "password": "scanuser",
    "host": "localhost"
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def add_scan(code: str, scanner_id: str):
    start_addScan = time.time()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO scans (code, scanner_id) VALUES (%s, %s)",
                (code, scanner_id)
            )
        conn.commit()
    print(f"\tintern: {time.time() - start_addScan}")
    start_addScan = time.time()
    notify_clients()
    print(f"\tnotify: {time.time() - start_addScan}")

def get_last_scans():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.code, st.firstname, st.lastname, st.class, s.scanner_id, s.timestamp
                FROM scans s
                LEFT JOIN students st ON s.code = st.code
                ORDER BY s.id DESC
                LIMIT 5
            """)
            return cur.fetchall()

def get_top_scans():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.code, st.firstname, st.lastname, st.class, COUNT(*) AS cnt
                FROM scans s
                LEFT JOIN students st ON s.code = st.code
                GROUP BY s.code, st.firstname, st.lastname, st.class
                ORDER BY cnt DESC
                LIMIT 5
            """)
            return cur.fetchall()

@app.route("/scan-client", methods=["POST"])
def scan_client():
    start_scan = time.time()
    code = request.form.get("code", "").strip()
    scanner_id = request.form.get("scanner_id", "").strip()
    data_dict = {"code": code, "scanner_id": scanner_id}
    if code and scanner_id:
        add_scan(code, scanner_id)
        print(f"\tscan: {time.time() - start_scan}")
        data_dict["status"] = "erfasst"
        return data_dict, 200
    data_dict["status"] = "ungültig"
    return data_dict, 400

@app.route("/scan", methods=["GET"])
def scan_form():
    return render_template("scan.html")

@app.route("/events")
def events():
    def event_stream():
        q = queue.Queue()
        clients.append(q)
        try:
            while True:
                try:
                    data = q.get(timeout=15)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    # keep connection alive
                    yield ":\n\n"
        except GeneratorExit:
            clients.remove(q)
    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

def notify_clients():
    for client in clients[:]:
        try:
            client.put_nowait("update")
        except queue.Full:
            clients.remove(client)

@app.route("/last")
def last():
    scans = get_last_scans()
    return render_template("last.html", scans=scans)

@app.route("/top")
def top():
    scans = get_top_scans()
    return render_template("top.html", scans=scans)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)