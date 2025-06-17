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
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO scans (code, scanner_id) VALUES (%s, %s)",
                (code, scanner_id)
            )
            
            cur.execute(
                "SELECT firstname, lastname, class FROM students WHERE code = %s",
                (code,)
            )
            result = cur.fetchone()
        conn.commit()
    notify_clients()
    
    if result:
        firstname, lastname, class_ = result
        return {
            "code": code,
            "firstname": firstname,
            "lastname": lastname,
            "class": class_,
            "scanner_id": scanner_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

def get_last_scans(number: int = 0):
    with get_connection() as conn:
        with conn.cursor() as cur:
            base_query = """
                SELECT s.code, st.firstname, st.lastname, st.class, s.scanner_id, s.timestamp
                FROM scans s
                LEFT JOIN students st ON s.code = st.code
                ORDER BY s.id DESC
            """
            if number > 0:
                cur.execute(base_query + " LIMIT %s", (number,))
            else:
                cur.execute(base_query)

            return cur.fetchall()

def get_top_students(number: int = 1):
    with get_connection() as conn:
        with conn.cursor() as cur:
            base_query = ("""
                SELECT s.code, st.firstname, st.lastname, st.class, COUNT(*) AS cnt
                FROM scans s
                LEFT JOIN students st ON s.code = st.code
                GROUP BY s.code, st.firstname, st.lastname, st.class
                ORDER BY cnt DESC
            """)
            if number > 0:
                cur.execute(base_query + " LIMIT %s", (number,))
            else:
                cur.execute(base_query)
                
            return cur.fetchall()

def get_top_classes(number: int = 1):
    with get_connection() as conn:
        with conn.cursor() as cur:
            base_query = ("""
                SELECT st.class, COUNT(*) AS cnt
                FROM scans s
                LEFT JOIN students st ON s.code = st.code
                GROUP BY st.class
                ORDER BY cnt DESC
            """)
            if number > 0:
                cur.execute(base_query + " LIMIT %s", (number,))
            else:
                cur.execute(base_query)
                
            return cur.fetchall()

@app.route("/scan-client", methods=["POST"])
def scan_client():
    start_time = time.time()
    code = request.form.get("code", "").strip()
    scanner_id = request.form.get("scanner_id", "").strip()
    data_dict = {"code": code, "scanner_id": scanner_id}
    if code and scanner_id:
        response_dict = add_scan(code, scanner_id)
        if response_dict:
            data_dict.update(response_dict)
            data_dict["status"] = "OK"
            status_code = 200
        else:
            data_dict["status"] = "Not Found"
            status_code = 404
    else:
        data_dict["status"] = "Bad Request"
        status_code = 400
    print(f"scan time: {time.time() - start_time}")
    return data_dict, status_code

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
def last_scans():
    scans = get_last_scans(5)
    return render_template("last.html", title="Letzte 5 Scans", scans=scans)

@app.route("/all")
def all_scans():
    scans = get_last_scans(0)
    return render_template("last.html", title="Alle Scans", scans=scans)

@app.route("/top-students")
def top_students():
    top_number  = 5
    students = get_top_students(top_number)
    return render_template("top-students.html", title=f"Top {top_number} Schüler*innnen", data=students)

@app.route("/top-classes")
def top_classes():
    top_number  = 10
    classes = get_top_classes(top_number)
    return render_template("top-classes.html", title=f"Top {top_number} Klassen", data=classes)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)