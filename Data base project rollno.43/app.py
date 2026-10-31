import math
import streamlit as st
import pyodbc
import pandas as pd
import base64


# =============================================================================
# PAGE SETTINGS
# =============================================================================

st.set_page_config(
    page_title="UAJK DMC Portal",
    page_icon="🎓",
    layout="wide"
)


# =============================================================================
# CONSTANTS
# =============================================================================

SEMESTERS = [f"Semester {i}" for i in range(1, 9)]

GRADE_SCALE = [
    (90.0, 4.0, "A+"),
    (80.0, 4.0, "A"),
    (72.5, 3.7, "B+"),
    (65.0, 3.2, "B"),
    (50.0, 2.0, "C"),
    (0.0, 0.0, "F"),
]


# =============================================================================
# GRADE CALCULATION
# =============================================================================

def get_grade_info(marks, total_marks):

    if (
        total_marks is None
        or pd.isna(total_marks)
        or total_marks <= 0
    ):
        return 0.0, "W"

    pct = (
        float(marks)
        /
        float(total_marks)
        *
        100
    )

    pct = math.floor(pct * 10 + 0.5) / 10

    for min_pct, gp, letter in GRADE_SCALE:

        if pct >= min_pct:
            return gp, letter

    return 0.0, "F"


# =============================================================================
# NUMBER FORMAT
# =============================================================================

def fmt_num(x):

    if x is None or pd.isna(x):
        return "0"

    x = float(x)

    if x == int(x):
        return str(int(x))

    return f"{x:.1f}"


# =============================================================================
# LOGO
# =============================================================================

def get_image_base64(path):

    try:

        with open(path, "rb") as f:
            return base64.b64encode(
                f.read()
            ).decode()

    except Exception:

        return ""


# =============================================================================
# SQL CONNECTION
# =============================================================================

def get_connection():

    conn_str = (
        "Driver={ODBC Driver 17 for SQL Server};"
        "Server=AHSAN-LAPTOP\\SQLEXPRESS04;"
        "Database=StudentDMCDB;"
        "Trusted_Connection=yes;"
    )

    return pyodbc.connect(conn_str)
try:
    conn = get_connection()
    conn.close()
    st.success("✅ SQL Server Connected Successfully")
except Exception as e:
    st.error(f"❌ SQL Server Connection Failed: {e}")

# =============================================================================
# LOAD MARKS
# =============================================================================

def load_marks(conn, student_id):

    df = pd.read_sql(
        """
        SELECT *
        FROM StudentMarks
        WHERE student_id = ?
        """,
        conn,
        params=[int(student_id)]
    )

    if df.empty:
        return df

    df["course_code"] = (
        df["course_code"]
        .fillna("")
        .astype(str)
    )

    df["course_title"] = (
        df["course_title"]
        .fillna("")
        .astype(str)
    )

    df["credit_hours"] = (
        pd.to_numeric(
            df["credit_hours"],
            errors="coerce"
        )
        .fillna(3)
        .astype(int)
    )

    df["total_marks"] = (
        pd.to_numeric(
            df["total_marks"],
            errors="coerce"
        )
        .fillna(100)
        .astype(int)
    )

    df["marks_obtained"] = (
        pd.to_numeric(
            df["marks_obtained"],
            errors="coerce"
        )
        .fillna(0)
        .astype(float)
    )

    return df


# =============================================================================
# REPLACE MARKS
# =============================================================================

def replace_marks(cursor, student_id, subjects):

    cursor.execute(
        """
        DELETE FROM StudentMarks
        WHERE student_id = ?
        """,
        (student_id,)
    )

    for s in subjects:

        cursor.execute(
            """
            INSERT INTO StudentMarks
            (
                student_id,
                course_code,
                course_title,
                credit_hours,
                total_marks,
                marks_obtained,
                grade_point,
                letter_grade
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                s["code"],
                s["title"],
                s["ch"],
                s["total"],
                s["obtained"],
                s["gp"],
                s["letter"]
            )
        )


# =============================================================================
# SIDEBAR
# =============================================================================

st.sidebar.title("🏛️ UAJK DMC System")

app_mode = st.sidebar.radio(
    "Select Portal",
    [
        "🔍 Search & View DMC",
        "⚙️ Admin (Add Record)",
        "✏️ Admin (Edit Record)",
        "🗑️ Admin (Manage & Delete Records)",
    ],
)


# =============================================================================
# 1. SEARCH & VIEW DMC
# =============================================================================

if app_mode == "🔍 Search & View DMC":

    st.title("🎓 Student DMC Verification Portal")

    search_reg = st.text_input(
        "Enter Student Registration Number to search:"
    )

    search_semester = st.selectbox(
        "Select Semester:",
        SEMESTERS
    )

    if st.button(
        "Generate Result Card",
        type="primary"
    ) and search_reg:

        conn = get_connection()

        # -------------------------------------------------------------
        # IMPORTANT:
        # Search by Registration Number + Semester
        # -------------------------------------------------------------

        student_df = pd.read_sql(
            """
            SELECT *
            FROM Students
            WHERE reg_no = ?
            AND semester = ?
            """,
            conn,
            params=[
                search_reg.strip(),
                search_semester
            ]
        )

        if student_df.empty:

            st.error(
                f"❌ No record found for "
                f"{search_reg.strip()} - "
                f"{search_semester}"
            )

            conn.close()

        else:

            s_data = student_df.iloc[0].fillna("")

            student_id = int(
                s_data["student_id"]
            )

            marks_df = load_marks(
                conn,
                student_id
            )

            conn.close()

            if marks_df.empty:

                st.warning(
                    "⚠️ Student exists but no subjects "
                    "or marks have been added."
                )

            else:

                # ---------------------------------------------------------
                # RECALCULATE GRADES
                # ---------------------------------------------------------

                grades = marks_df.apply(
                    lambda r: get_grade_info(
                        r["marks_obtained"],
                        r["total_marks"]
                    ),
                    axis=1
                )

                marks_df["grade_point"] = [
                    g[0] for g in grades
                ]

                marks_df["letter_grade"] = [
                    g[1] for g in grades
                ]

                valid_marks = marks_df[
                    (marks_df["total_marks"] > 0)
                    &
                    (marks_df["letter_grade"] != "W")
                ]

                grand_total = float(
                    valid_marks["total_marks"].sum()
                )

                obtained_total = float(
                    valid_marks["marks_obtained"].sum()
                )

                if grand_total > 0:

                    sem_percentage = (
                        math.floor(
                            obtained_total
                            /
                            grand_total
                            *
                            1000
                            + 0.5
                        )
                        /
                        10
                    )

                else:

                    sem_percentage = 0.0

                total_credits = float(
                    valid_marks["credit_hours"].sum()
                )

                if total_credits > 0:

                    gpa = round(
                        float(
                            (
                                valid_marks["grade_point"]
                                *
                                valid_marks["credit_hours"]
                            ).sum()
                        )
                        /
                        total_credits,
                        2
                    )

                else:

                    gpa = 0.0

                # Current design:
                # CGPA for one semester record = GPA
                cgpa = gpa

                if grand_total > 0:

                    sem_letter = get_grade_info(
                        obtained_total,
                        grand_total
                    )[1]

                else:

                    sem_letter = "-"

                cum_letter = sem_letter

                has_fail = (
                    valid_marks["letter_grade"] == "F"
                ).any()

                remarks = (
                    "Not Promoted"
                    if has_fail or valid_marks.empty
                    else "Promoted"
                )

                # ---------------------------------------------------------
                # SUBJECT ROWS
                # ---------------------------------------------------------

                rows_html = ""

                for _, row in marks_df.iterrows():

                    if row["total_marks"] > 0:

                        pct = math.floor(
                            row["marks_obtained"]
                            /
                            row["total_marks"]
                            *
                            1000
                            + 0.5
                        ) / 10

                        percentage_str = f"{pct:.1f}"

                    else:

                        percentage_str = "-"

                    rows_html += f"""
                    <tr>

                        <td style="text-align:center;">
                            {row['course_code']}
                        </td>

                        <td>
                            {row['course_title']}
                        </td>

                        <td style="text-align:center;">
                            {fmt_num(row['credit_hours'])}
                        </td>

                        <td style="text-align:center;">
                            {fmt_num(row['total_marks'])}
                        </td>

                        <td style="text-align:center;">
                            {fmt_num(row['marks_obtained'])}
                        </td>

                        <td style="text-align:center;">
                            {percentage_str}
                        </td>

                        <td style="text-align:center;">
                            {row['grade_point']:.2f}
                        </td>

                        <td style="text-align:center;">
                            {row['letter_grade']}
                        </td>

                    </tr>
                    """

                # ---------------------------------------------------------
                # LOGO
                # ---------------------------------------------------------

                logo_b64 = get_image_base64(
                    "uajk_logo.png"
                )

                if logo_b64:

                    logo_src = (
                        f"data:image/png;base64,"
                        f"{logo_b64}"
                    )

                else:

                    logo_src = (
                        "https://uajk.edu.pk/"
                        "wp-content/uploads/2022/12/"
                        "ajku-logo-min.png"
                    )

                # ---------------------------------------------------------
                # DMC
                # ---------------------------------------------------------

                dmc_html = f"""
                <style>

                    .dmc-card {{
                        background-color: #ffffff;
                        color: #000000;
                        padding: 30px;
                        border: 2px solid #333;
                        font-family:
                            'Times New Roman',
                            Times,
                            serif;

                        width: 100%;
                        max-width: 850px;
                        margin: 0 auto;
                    }}

                    .header-title {{
                        text-align: center;
                        font-weight: bold;
                        font-size: 20px;
                    }}

                    .header-sub {{
                        text-align: center;
                        font-weight: bold;
                        font-size: 14px;
                        margin-bottom: 10px;
                    }}

                    .meta-table,
                    .results-table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-top: 10px;
                    }}

                    .meta-table td {{
                        padding: 4px;
                        font-size: 14px;
                    }}

                    .results-table th {{
                        background-color: #d3d3d3;
                        border: 1px solid #000;
                        padding: 6px;
                        font-size: 13px;
                        text-align: center;
                    }}

                    .results-table td {{
                        border: 1px dashed #777;
                        border-left: 1px solid #000;
                        border-right: 1px solid #000;
                        padding: 6px;
                        font-size: 13px;
                    }}

                    .footer-box {{
                        border: 1px solid #000;
                        padding: 8px;
                        font-size: 11px;
                        margin-top: 20px;
                        width: 65%;
                        float: left;
                    }}

                </style>

                <div class="dmc-card">

                    <div class="header-title">
                        The University of Azad Jammu and Kashmir Muzaffarabad
                    </div>

                    <div class="header-sub">
                        DEPARTMENT OF COMPUTER SCIENCES AND IT
                    </div>

                    <div style="
                        text-align:center;
                        font-weight:bold;
                        font-size:15px;
                        text-decoration:underline;
                    ">
                        Semester Result Card
                    </div>

                    <div style="
                        display:flex;
                        justify-content:space-between;
                        align-items:center;
                        margin-top:15px;
                    ">

                        <div>
                            No: ______________________
                        </div>

                        <img
                            src="{logo_src}"
                            width="85"
                            alt="UAJK Logo"
                        >

                        <div>
                            Date: {s_data['issue_date']}
                        </div>

                    </div>

                    <table class="meta-table">

                        <tr>
                            <td>
                                <b>Name:</b> {s_data['name']}
                            </td>

                            <td>
                                <b>Roll No:</b> {s_data['roll_no']}
                            </td>
                        </tr>

                        <tr>
                            <td>
                                <b>Father's Name:</b>
                                {s_data['father_name']}
                            </td>

                            <td>
                                <b>Registration No:</b>
                                {s_data['reg_no']}
                            </td>
                        </tr>

                        <tr>
                            <td>
                                <b>Program:</b>
                                {s_data['program']}
                            </td>

                            <td>
                                <b>Semester:</b>
                                {s_data['semester']}
                            </td>
                        </tr>

                        <tr>
                            <td colspan="2">
                                <b>Session:</b>
                                {s_data['session']}
                            </td>
                        </tr>

                    </table>

                    <table
                        class="results-table"
                        style="margin-top:15px;"
                    >

                        <thead>

                            <tr>
                                <th>Course Code</th>
                                <th>Course Title</th>
                                <th>Credit Hours</th>
                                <th>Total Marks</th>
                                <th>Marks Obtained</th>
                                <th>Marks %age</th>
                                <th>Grade Point</th>
                                <th>Letter Grade</th>
                            </tr>

                        </thead>

                        <tbody>
                            {rows_html}
                        </tbody>

                    </table>

                    <table style="
                        width:100%;
                        margin-top:20px;
                        font-size:13px;
                        font-weight:bold;
                    ">

                        <tr>
                            <td>Semester Grand Total:</td>
                            <td>{fmt_num(grand_total)}</td>

                            <td>Semester Marks Obtained:</td>
                            <td>{fmt_num(obtained_total)}</td>
                        </tr>

                        <tr>
                            <td>Grade Point Average (GPA):</td>
                            <td>{gpa:.2f}</td>

                            <td>Letter Grade (Semester):</td>
                            <td>{sem_letter}</td>
                        </tr>

                        <tr>
                            <td>Cumulative Grade Point Average (CGPA):</td>
                            <td>{cgpa:.2f}</td>

                            <td>Letter Grade (Cumulative):</td>
                            <td>{cum_letter}</td>
                        </tr>

                        <tr>
                            <td>Percentage (Semester):</td>
                            <td>{sem_percentage:.1f}%</td>

                            <td>Remarks:</td>
                            <td>{remarks}</td>
                        </tr>

                    </table>

                    <div style="
                        margin-top:25px;
                        display:flex;
                        justify-content:space-between;
                        align-items:flex-end;
                    ">

                        <div class="footer-box">

                            <b>Note:</b>

                            Grade: 90.0% and above = A+;
                            80.0 to 89.9% = A;
                            72.5 to 79.9% = B+;
                            65.0 to 72.4% = B;
                            50.0 to 64.9% = C;
                            below 50.0% = F;
                            Course Withdrawn = W

                            <br><br>

                            Errors and Omissions Excepted.

                        </div>

                        <div style="text-align:center;">

                            __________________________

                            <br>

                            <b>
                                Controller of Examinations
                            </b>

                        </div>

                    </div>

                </div>
                """

                st.components.v1.html(
                    dmc_html,
                    height=850,
                    scrolling=True
                )


# =============================================================================
# 2. ADMIN - ADD RECORD
# =============================================================================

elif app_mode == "⚙️ Admin (Add Record)":

    st.title("⚙️ Admin Portal: Add Student Record")

    st.caption(
        "Same Registration Number can be used for different semesters."
    )

    # -------------------------------------------------------------
    # Number of subjects
    # -------------------------------------------------------------

    if "num_subjects" not in st.session_state:
        st.session_state.num_subjects = 5

    # -------------------------------------------------------------
    # Student details
    # -------------------------------------------------------------

    st.markdown(
        "### 📋 1. Student Personal & Academic Details"
    )

    c1, c2 = st.columns(2)

    reg_no = c1.text_input(
        "Registration No*"
    )

    roll_no = c2.text_input(
        "Roll No*"
    )

    name = c1.text_input(
        "Student Name*"
    )

    father_name = c2.text_input(
        "Father's Name*"
    )

    program = c1.text_input(
        "Program*"
    )

    semester = c2.selectbox(
        "Semester*",
        SEMESTERS
    )

    session = st.text_input(
        "Session Info*"
    )

    issue_date = st.date_input(
        "DMC Date"
    )

    # -------------------------------------------------------------
    # IMPORTANT:
    # Create a different key for every Registration + Semester.
    #
    # Therefore:
    #
    # FA22-BSCS-001 + Semester 1
    #
    # and
    #
    # FA22-BSCS-001 + Semester 2
    #
    # get completely different subject input boxes.
    # -------------------------------------------------------------

    student_key = (
        reg_no.strip().replace(" ", "_")
        + "_"
        + semester.replace(" ", "_")
    )

    st.markdown("---")

    st.markdown(
        "### 📚 2. Subject & Marks Entry"
    )

    st.info(
        f"📘 Adding subjects for: "
        f"**{semester}**"
    )

    subjects_input = []
    invalid_rows = []

    # -------------------------------------------------------------
    # SUBJECT INPUTS
    # -------------------------------------------------------------

    for i in range(
        1,
        st.session_state.num_subjects + 1
    ):

        col_code, col_title, col_ch, col_tot, col_obt = st.columns(
            [1.5, 3, 1, 1, 1]
        )

        code = col_code.text_input(
            f"Course Code {i}",
            key=f"{student_key}_code_{i}"
        )

        title = col_title.text_input(
            f"Course Title {i}",
            key=f"{student_key}_title_{i}"
        )

        ch = col_ch.number_input(
            f"Cr.Hr {i}",
            min_value=0,
            max_value=6,
            value=3,
            key=f"{student_key}_ch_{i}"
        )

        total = col_tot.number_input(
            f"Total Marks {i}",
            min_value=0,
            max_value=200,
            value=100,
            key=f"{student_key}_total_{i}"
        )

        obtained = col_obt.number_input(
            f"Obtained {i}",
            min_value=0.0,
            max_value=200.0,
            value=0.0,
            step=0.5,
            key=f"{student_key}_obtained_{i}"
        )

        if code.strip() and title.strip():

            if obtained > total:
                invalid_rows.append(i)

            gp, letter = get_grade_info(
                obtained,
                total
            )

            subjects_input.append(
                {
                    "code": code.strip(),
                    "title": title.strip(),
                    "ch": int(ch),
                    "total": int(total),
                    "obtained": float(obtained),
                    "gp": gp,
                    "letter": letter
                }
            )

    # -------------------------------------------------------------
    # ADD / REMOVE SUBJECT
    # -------------------------------------------------------------

    col_add, col_rem, _ = st.columns(
        [1.5, 1.5, 5]
    )

    if col_add.button(
        "➕ Add More Subject"
    ):

        st.session_state.num_subjects += 1

        st.rerun()

    if col_rem.button(
        "➖ Remove Subject"
    ):

        if st.session_state.num_subjects > 1:

            st.session_state.num_subjects -= 1

            st.rerun()

    st.markdown("---")

    # -------------------------------------------------------------
    # SAVE RECORD
    # -------------------------------------------------------------

    if st.button(
        "💾 Save Student Record to Database",
        type="primary"
    ):

        if (
            not reg_no.strip()
            or not name.strip()
            or not roll_no.strip()
        ):

            st.error(
                "⚠️ Registration No, Roll No, "
                "and Name are mandatory!"
            )

        elif len(subjects_input) == 0:

            st.error(
                "⚠️ Please enter at least one subject."
            )

        elif invalid_rows:

            st.error(
                f"⚠️ Obtained marks are greater than "
                f"total marks in row(s): {invalid_rows}"
            )

        else:

            try:

                conn = get_connection()

                cursor = conn.cursor()

                # ---------------------------------------------------------
                # IMPORTANT:
                # Check Registration + Semester,
                # NOT Registration alone.
                # ---------------------------------------------------------

                cursor.execute(
                    """
                    SELECT student_id
                    FROM Students
                    WHERE reg_no = ?
                    AND semester = ?
                    """,
                    (
                        reg_no.strip(),
                        semester
                    )
                )

                existing = cursor.fetchone()

                if existing:

                    conn.close()

                    st.error(
                        f"⚠️ {reg_no} already has a record "
                        f"for {semester}. "
                        f"Use Edit Record to modify it."
                    )

                else:

                    # -----------------------------------------------------
                    # Insert new semester record
                    # -----------------------------------------------------

                    cursor.execute(
                        """
                        INSERT INTO Students
                        (
                            reg_no,
                            roll_no,
                            name,
                            father_name,
                            program,
                            session,
                            semester,
                            issue_date
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            reg_no.strip(),
                            roll_no.strip(),
                            name.strip(),
                            father_name.strip(),
                            program.strip(),
                            session.strip(),
                            semester,
                            issue_date
                        )
                    )

                    # -----------------------------------------------------
                    # Get NEW student_id
                    # -----------------------------------------------------

                    cursor.execute(
                        """
                        SELECT student_id
                        FROM Students
                        WHERE reg_no = ?
                        AND semester = ?
                        """,
                        (
                            reg_no.strip(),
                            semester
                        )
                    )

                    student_id = cursor.fetchone()[0]

                    # -----------------------------------------------------
                    # Save semester subjects
                    # -----------------------------------------------------

                    replace_marks(
                        cursor,
                        student_id,
                        subjects_input
                    )

                    conn.commit()

                    conn.close()

                    st.success(
                        f"✅ {semester} saved successfully "
                        f"for {name} "
                        f"({reg_no}) with "
                        f"{len(subjects_input)} subjects!"
                    )

            except Exception as e:

                st.error(
                    f"❌ Database error: {e}"
                )


# =============================================================================
# 3. ADMIN - EDIT RECORD
# =============================================================================

elif app_mode == "✏️ Admin (Edit Record)":

    st.title("✏️ Edit Student Record")

    st.caption(
        "Select the student and semester you want to edit."
    )

    conn = get_connection()

    students_df = pd.read_sql(
        """
        SELECT
            student_id,
            reg_no,
            name,
            semester
        FROM Students
        ORDER BY reg_no, semester
        """,
        conn
    )

    if students_df.empty:

        st.info(
            "No student records found."
        )

        conn.close()

    else:

        # -------------------------------------------------------------
        # Show Registration + Semester
        # -------------------------------------------------------------

        labels = [
            f"{r.reg_no} - {r.name} - {r.semester}"
            for r in students_df.itertuples()
        ]

        choice = st.selectbox(
            "Select student and semester to edit:",
            labels
        )

        selected_index = labels.index(
            choice
        )

        sid = int(
            students_df.iloc[
                selected_index
            ]["student_id"]
        )

        s = pd.read_sql(
            """
            SELECT *
            FROM Students
            WHERE student_id = ?
            """,
            conn,
            params=[sid]
        ).iloc[0].fillna("")

        marks_df = load_marks(
            conn,
            sid
        )

        conn.close()

        # -------------------------------------------------------------
        # Student Details
        # -------------------------------------------------------------

        st.markdown(
            "### 📋 1. Student Details"
        )

        c1, c2 = st.columns(2)

        c1.text_input(
            "Registration No",
            value=str(s["reg_no"]),
            disabled=True
        )

        e_roll = c2.text_input(
            "Roll No*",
            value=str(s["roll_no"])
        )

        e_name = c1.text_input(
            "Student Name*",
            value=str(s["name"])
        )

        e_father = c2.text_input(
            "Father's Name*",
            value=str(s["father_name"])
        )

        e_program = c1.text_input(
            "Program*",
            value=str(s["program"])
        )

        sem_idx = (
            SEMESTERS.index(s["semester"])
            if s["semester"] in SEMESTERS
            else 0
        )

        e_sem = c2.selectbox(
            "Semester*",
            SEMESTERS,
            index=sem_idx
        )

        e_session = st.text_input(
            "Session Info*",
            value=str(s["session"])
        )

        try:

            default_date = pd.to_datetime(
                s["issue_date"]
            ).date()

        except Exception:

            default_date = pd.Timestamp.today().date()

        e_date = st.date_input(
            "DMC Date",
            value=default_date
        )

        # -------------------------------------------------------------
        # Subjects
        # -------------------------------------------------------------

        st.markdown("---")

        st.markdown(
            "### 📚 2. Subjects & Marks"
        )

        editor_df = marks_df[
            [
                "course_code",
                "course_title",
                "credit_hours",
                "total_marks",
                "marks_obtained"
            ]
        ].reset_index(drop=True)

        edited = st.data_editor(
            editor_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={

                "course_code":
                    st.column_config.TextColumn(
                        "Course Code",
                        required=True
                    ),

                "course_title":
                    st.column_config.TextColumn(
                        "Course Title",
                        required=True,
                        width="large"
                    ),

                "credit_hours":
                    st.column_config.NumberColumn(
                        "Cr.Hr",
                        min_value=0,
                        max_value=6,
                        step=1,
                        default=3
                    ),

                "total_marks":
                    st.column_config.NumberColumn(
                        "Total Marks",
                        min_value=0,
                        max_value=200,
                        step=1,
                        default=100
                    ),

                "marks_obtained":
                    st.column_config.NumberColumn(
                        "Marks Obtained",
                        min_value=0,
                        max_value=200,
                        step=0.5,
                        default=0
                    )
            }
        )

        # -------------------------------------------------------------
        # UPDATE
        # -------------------------------------------------------------

        if st.button(
            "💾 Update Record",
            type="primary"
        ):

            subjects = []
            bad_rows = []

            for idx, r in edited.iterrows():

                code = (
                    ""
                    if pd.isna(r["course_code"])
                    else str(
                        r["course_code"]
                    ).strip()
                )

                title = (
                    ""
                    if pd.isna(r["course_title"])
                    else str(
                        r["course_title"]
                    ).strip()
                )

                if not code and not title:
                    continue

                ch = (
                    3
                    if pd.isna(r["credit_hours"])
                    else int(r["credit_hours"])
                )

                total = (
                    100
                    if pd.isna(r["total_marks"])
                    else int(r["total_marks"])
                )

                obtained = (
                    0.0
                    if pd.isna(r["marks_obtained"])
                    else float(r["marks_obtained"])
                )

                if (
                    not code
                    or not title
                    or obtained > total
                ):

                    bad_rows.append(
                        idx + 1
                    )

                    continue

                gp, letter = get_grade_info(
                    obtained,
                    total
                )

                subjects.append(
                    {
                        "code": code,
                        "title": title,
                        "ch": ch,
                        "total": total,
                        "obtained": obtained,
                        "gp": gp,
                        "letter": letter
                    }
                )

            if not e_roll.strip() or not e_name.strip():

                st.error(
                    "⚠️ Roll No and Name are mandatory."
                )

            elif bad_rows:

                st.error(
                    f"⚠️ Fix row(s): {bad_rows}"
                )

            elif not subjects:

                st.error(
                    "⚠️ Add at least one subject."
                )

            else:

                try:

                    conn = get_connection()

                    cursor = conn.cursor()

                    # -----------------------------------------------------
                    # If semester is changed during editing,
                    # make sure another record doesn't already exist.
                    # -----------------------------------------------------

                    cursor.execute(
                        """
                        SELECT student_id
                        FROM Students
                        WHERE reg_no = ?
                        AND semester = ?
                        AND student_id <> ?
                        """,
                        (
                            str(s["reg_no"]).strip(),
                            e_sem,
                            sid
                        )
                    )

                    duplicate = cursor.fetchone()

                    if duplicate:

                        st.error(
                            f"⚠️ {s['reg_no']} already has "
                            f"a record for {e_sem}."
                        )

                        conn.close()

                    else:

                        cursor.execute(
                            """
                            UPDATE Students
                            SET
                                roll_no=?,
                                name=?,
                                father_name=?,
                                program=?,
                                session=?,
                                semester=?,
                                issue_date=?
                            WHERE student_id=?
                            """,
                            (
                                e_roll.strip(),
                                e_name.strip(),
                                e_father.strip(),
                                e_program.strip(),
                                e_session.strip(),
                                e_sem,
                                e_date,
                                sid
                            )
                        )

                        replace_marks(
                            cursor,
                            sid,
                            subjects
                        )

                        conn.commit()

                        conn.close()

                        st.success(
                            f"✅ {e_name}'s "
                            f"{e_sem} record updated."
                        )

                except Exception as e:

                    st.error(
                        f"❌ Database error: {e}"
                    )


# =============================================================================
# 4. MANAGE & DELETE
# =============================================================================

elif app_mode == "🗑️ Admin (Manage & Delete Records)":

    st.title(
        "🗑️ Manage & Delete Student Records"
    )

    st.caption(
        "Each semester is treated as a separate DMC record."
    )

    conn = get_connection()

    students_df = pd.read_sql(
        """
        SELECT
            student_id,
            reg_no,
            roll_no,
            name,
            father_name,
            program,
            semester
        FROM Students
        ORDER BY reg_no, semester
        """,
        conn
    )

    if students_df.empty:

        st.info(
            "No student records found."
        )

    else:

        st.dataframe(
            students_df,
            use_container_width=True
        )

        st.markdown("---")

        st.subheader(
            "🔥 Delete Semester Record"
        )

        # -------------------------------------------------------------
        # Select exact student + semester
        # -------------------------------------------------------------

        delete_labels = [
            f"{r.reg_no} - {r.name} - {r.semester}"
            for r in students_df.itertuples()
        ]

        delete_choice = st.selectbox(
            "Select record to delete:",
            delete_labels
        )

        delete_index = delete_labels.index(
            delete_choice
        )

        delete_student_id = int(
            students_df.iloc[
                delete_index
            ]["student_id"]
        )

        confirm_check = st.checkbox(
            "I confirm that I want to permanently "
            "delete this semester record and its marks."
        )

        if st.button(
            "🗑️ Permanently Delete Record",
            type="primary"
        ):

            if not confirm_check:

                st.warning(
                    "⚠️ Please confirm before deleting."
                )

            else:

                try:

                    cursor = conn.cursor()

                    # -----------------------------------------------------
                    # Delete only marks belonging to selected semester
                    # -----------------------------------------------------

                    cursor.execute(
                        """
                        DELETE FROM StudentMarks
                        WHERE student_id = ?
                        """,
                        (delete_student_id,)
                    )

                    # -----------------------------------------------------
                    # Delete only selected semester/student record
                    # -----------------------------------------------------

                    cursor.execute(
                        """
                        DELETE FROM Students
                        WHERE student_id = ?
                        """,
                        (delete_student_id,)
                    )

                    conn.commit()

                    st.success(
                        "✅ Selected semester record "
                        "has been deleted."
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        f"❌ Failed to delete record: {e}"
                    )

    conn.close()