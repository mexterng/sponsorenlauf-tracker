from flask import Flask, request, render_template, Response, stream_with_context, jsonify
import psycopg2, queue, time

app = Flask(__name__)
clients = []

DB_CONFIG = {
    "dbname": "demo1",
    "user": "scanuser",
    "password": "scanuser",
    "host": "localhost",
}


def get_connection():
    # Establish and return a new DB connection
    return psycopg2.connect(**DB_CONFIG)


def query_database(query: str, params: tuple = ()):
     # Execute a query and return all rows
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def add_scan(code: str, scanner_id: str):
    # Insert new scan and return student data if available
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO scans (code, scanner_id) VALUES (%s, %s)",
                (code, scanner_id),
            )
            cur.execute(
                "SELECT firstname, lastname, class FROM students WHERE code = %s",
                (code,),
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
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }


def get_last_scans(number: int = 0, failures: bool = False):
    # Return recent scans with or without failed lookups
    base_query = """
        SELECT s.code, st.firstname, st.lastname, st.class, s.scanner_id, s.timestamp
        FROM scans s
        LEFT JOIN students st ON s.code = st.code
    """
    where_clause = ""
    if not failures:
        where_clause = " WHERE st.firstname IS NOT NULL"

    order_clause = " ORDER BY s.id DESC"

    limit_clause = ""
    params = ()

    if number > 0:
        limit_clause = " LIMIT %s"
        params = (number,)

    full_query = base_query + where_clause + order_clause + limit_clause

    return query_database(full_query, params)


def get_top_students(number: int = 1, failures: bool = False):
     # Return most scanned students
    base_query = """
        SELECT s.code, st.firstname, st.lastname, st.class, COUNT(*) AS cnt
        FROM scans s
        LEFT JOIN students st ON s.code = st.code
    """

    where_clause = ""
    if not failures:
        where_clause = " WHERE st.firstname IS NOT NULL"

    group_order_clause = """ 
        GROUP BY s.code, st.firstname, st.lastname, st.class
        ORDER BY cnt DESC
    """

    limit_clause = ""
    params = ()

    if number > 0:
        limit_clause = " LIMIT %s"
        params = (number,)

    full_query = base_query + where_clause + group_order_clause + limit_clause

    return query_database(full_query, params)


def get_top_classes(number: int = 1, failures: bool = False):
    # Return classes with most scans
    base_query = """ 
        SELECT st.class, COUNT(*) AS cnt
        FROM scans s
        LEFT JOIN students st ON s.code = st.code
    """

    where_clause = ""
    if not failures:
        where_clause = " WHERE st.class IS NOT NULL"

    group_order_clause = """ 
        GROUP BY st.class
        ORDER BY cnt DESC
    """

    limit_clause = ""
    params = ()

    if number > 0:
        limit_clause = " LIMIT %s"
        params = (number,)

    full_query = (
        base_query
        + where_clause
        + group_order_clause
        + limit_clause
    )
    
    return query_database(full_query, params)


@app.route("/scan-client", methods=["POST"])
def scan_client():
    # Handle scan from client
    start_time = time.time()
    code = request.form.get("code", "").strip()
    scanner_id = request.form.get("scanner_id", "").strip()
    
    if not code or not scanner_id:
        return jsonify({"status": "Bad Request"}), 400

    response_dict = add_scan(code, scanner_id)
    if response_dict:
        response_dict["status"] = "OK"
        status_code = 200
    else:
        response_dict = {"code": code, "scanner_id": scanner_id, "status": "Not Found"}
        status_code = 404

    print(f"scan time: {time.time() - start_time}")
    return jsonify(response_dict), status_code


@app.route("/scan", methods=["GET"])
def scan_form():
    # Return scan form page
    return render_template("scan.html")


@app.route("/events", methods=["GET"])
def events():
    # Server-sent events endpoint
    def event_stream():
        q = queue.Queue()
        clients.append(q)
        try:
            while True:
                try:
                    data = q.get(timeout=15)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ":\n\n"  # keep-alive
        except GeneratorExit:
            clients.remove(q)

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")


def notify_clients():
    # Push update event to all clients
    for client in clients[:]:
        try:
            client.put_nowait("update")
        except queue.Full:
            clients.remove(client)


@app.route("/last", methods=["GET"])
def last_scans():
    limit = request.args.get("limit", default=5, type=int)
    failures = request.args.get("failures", default=False, type=bool)
    scans = get_last_scans(limit, failures=failures)
    return render_template("last.html", title=f"Letzte {limit} Scans", scans=scans)


@app.route("/all", methods=["GET"])
def all_scans():
    # Render page for all scans
    failures = request.args.get("failures", default=False, type=bool)
    scans = get_last_scans(0, failures=failures)
    return render_template("last.html", title="Alle Scans", scans=scans)


@app.route("/top-students", methods=["GET"])
def top_students():
    # Render page for top scanned students
    limit = request.args.get("limit", default=5, type=int)
    failures = request.args.get("failures", default=False, type=bool)
    students = get_top_students(limit, failures=failures)
    return render_template(
        "top-students.html", title=f"Top {limit} Schüler*innnen", data=students
    )


@app.route("/top-classes", methods=["GET"])
def top_classes():
    # Render page for top scanned classes
    limit = request.args.get("limit", default=10, type=int)
    failures = request.args.get("failures", default=False, type=bool)
    classes = get_top_classes(limit, failures=failures)
    return render_template(
        "top-classes.html", title=f"Top {limit} Klassen", data=classes
    )


if __name__ == "__main__":
    # Start Flask app
    app.run(host="0.0.0.0", port=8080, debug=False)