from flask import (
    Flask,
    request,
    render_template,
    Response,
    stream_with_context,
    jsonify,
)
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
    def insert_scan():
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Insert new scan
                cur.execute(
                    "INSERT INTO scans (code, scanner_id) VALUES (%s, %s)",
                    (code, scanner_id),
                )
            conn.commit()
        notify_clients()
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Try to get student info
            cur.execute(
                "SELECT firstname, lastname, class FROM students WHERE code = %s",
                (code,),
            )

            student_data = cur.fetchone()
        conn.commit()

    if student_data:
        firstname, lastname, class_ = student_data
        response = {
            "code": code,
            "firstname": firstname,
            "lastname": lastname,
            "class": class_,
            "scanner_id": scanner_id,
        }
        # Check for recent scan to enforce cooldown
        cooldown_query = """
            SELECT 1 FROM scans
            WHERE code = %s AND timestamp >= NOW() - INTERVAL '120 seconds'
            LIMIT 1
        """
        if query_database(cooldown_query, (code,)):
            # Cooldown active, scan ignored
            response.update({
                "status": "Cooldown",
                "status_code": 429,
            })
        else:
            insert_scan()
            response.update({
                "status": "OK",
                "status_code": 200,
            })
    else:
        insert_scan()
        response = {
            "code": code,
            "scanner_id": scanner_id,
            "status": "Not Found",
            "status_code": 404,
        }
        
    response["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")

    return response


def get_last_scans(limit: int = 0, failures: bool = False):
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

    if limit > 0:
        limit_clause = " LIMIT %s"
        params = (limit,)

    full_query = base_query + where_clause + order_clause + limit_clause

    return query_database(full_query, params)


def limit_filter(limit: int):
    pass

def failures_filter(failures: bool):
    pass

def grade_levels_filter(grade_levels = []):
    pass


def get_top_students(limit: int = 1, failures: bool = False, grade_levels = []):
    # Return most scanned students
    base_query = """
        SELECT s.code, st.firstname, st.lastname, st.class, COUNT(*) AS cnt
        FROM scans s
        LEFT JOIN students st ON s.code = st.code
    """

    where_clauses = []
    params = []
    if not failures:
        where_clauses.append("st.firstname IS NOT NULL")
    
    if grade_levels:
        like_clauses = []
        for level in grade_levels:
            like_clauses.append("st.class LIKE %s")
            params.append(f"{level}%")  # e. g. "5%" for classes like 5a, 5b etc.
        where_clauses.append("(" + " OR ".join(like_clauses) + ")")

    where_clause = ""
    if where_clauses:
        where_clause = " WHERE " + " AND ".join(where_clauses)

    group_order_clause = """ 
        GROUP BY s.code, st.firstname, st.lastname, st.class
        ORDER BY cnt DESC
    """

    limit_clause = ""

    if limit > 0:
        limit_clause = " LIMIT %s"
        params.append(limit)

    full_query = base_query + where_clause + group_order_clause + limit_clause

    return query_database(full_query, tuple(params))


def get_top_classes(number: int = 1, failures: bool = False, grade_levels = []):
    # Return classes with most scans
    base_query = """ 
        SELECT st.class, COUNT(*) AS cnt
        FROM scans s
        LEFT JOIN students st ON s.code = st.code
    """

    where_clauses = []
    params = []
    if not failures:
        where_clauses.append("st.class IS NOT NULL")
        
    if grade_levels:
        like_clauses = []
        for level in grade_levels:
            like_clauses.append("st.class LIKE %s")
            params.append(f"{level}%")  # e. g. "5%" for classes like 5a, 5b etc.
        where_clauses.append("(" + " OR ".join(like_clauses) + ")")

    where_clause = ""
    if where_clauses:
        where_clause = " WHERE " + " AND ".join(where_clauses)

    group_order_clause = """ 
        GROUP BY st.class
        ORDER BY cnt DESC
    """

    limit_clause = ""

    if number > 0:
        limit_clause = " LIMIT %s"
        params.append(number)

    full_query = base_query + where_clause + group_order_clause + limit_clause

    return query_database(full_query, tuple(params))


@app.route("/scan-client", methods=["POST"])
def scan_client():
    # Handle scan from client
    start_time = time.time()
    code = request.form.get("code", "").strip()
    scanner_id = request.form.get("scanner_id", "").strip()

    if not code or not scanner_id:
        return jsonify({"status": "Bad Request", "status_code": 400}), 400

    response_dict = add_scan(code, scanner_id)

    print(f"scan time: {time.time() - start_time}")
    return jsonify(response_dict), response_dict["status_code"]


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


# helper for parse grade levels
def parse_grade_levels(param: str) -> list[int]:
    result = []
    if not param:
        return result
    for part in param.split(','):
        if '-' in part:
            start, end = part.split('-')
            result.extend(range(int(start), int(end) + 1))
        else:
            result.append(int(part))
    return sorted(set(result))


@app.route("/top-students", methods=["GET"])
def top_students():    
    # Render page for top scanned students
    limit = request.args.get("limit", default=5, type=int)
    failures = request.args.get("failures", default=False, type=bool)
    grade_levels = request.args.get("grade-levels", default="", type=str)
    grade_levels = parse_grade_levels(grade_levels)
    students = get_top_students(limit, failures=failures, grade_levels=grade_levels)
    return render_template("top-students.html", title=f"Top {limit} Schüler*innnen", data=students)


@app.route("/top-classes", methods=["GET"])
def top_classes():
    # Render page for top scanned classes
    limit = request.args.get("limit", default=10, type=int)
    failures = request.args.get("failures", default=False, type=bool)
    grade_levels = request.args.get("grade-levels", default="", type=str)
    grade_levels = parse_grade_levels(grade_levels)
    classes = get_top_classes(limit, failures=failures, grade_levels=grade_levels)
    return render_template("top-classes.html", title=f"Top {limit} Klassen", data=classes)


if __name__ == "__main__":
    # Start Flask app
    app.run(host="0.0.0.0", port=8080, debug=False)
