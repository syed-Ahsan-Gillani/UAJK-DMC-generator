/* ============================================================
   UAJK DMC PORTAL
   EXISTING DATABASE UPDATE SCRIPT
   ============================================================

   Database:
       StudentDMCDB

   Purpose:
       Allow same Registration Number in multiple semesters.

   Correct rule:

       FA22-BSCS-001 + Semester 1   = allowed
       FA22-BSCS-001 + Semester 2   = allowed
       FA22-BSCS-001 + Semester 3   = allowed
       FA22-BSCS-001 + Semester 4   = allowed

       FA22-BSCS-001 + Semester 1   = duplicate/not allowed

   IMPORTANT:
       This script DOES NOT DROP Students or StudentMarks.
       Existing student/marks data is preserved.
   ============================================================ */


USE StudentDMCDB;
GO


/* ============================================================
   1. CHECK REQUIRED TABLES
   ============================================================ */

IF OBJECT_ID('dbo.Students', 'U') IS NULL
BEGIN
    PRINT 'ERROR: Students table does not exist.';
    RETURN;
END;
GO

IF OBJECT_ID('dbo.StudentMarks', 'U') IS NULL
BEGIN
    PRINT 'ERROR: StudentMarks table does not exist.';
    RETURN;
END;
GO


/* ============================================================
   2. SHOW CURRENT STUDENTS
   ============================================================ */

SELECT
    student_id,
    reg_no,
    roll_no,
    name,
    father_name,
    program,
    session,
    semester,
    issue_date
FROM dbo.Students
ORDER BY reg_no, semester;
GO


/* ============================================================
   3. CHECK FOR DUPLICATE REGISTRATION + SEMESTER
   ============================================================

   This MUST return zero rows before creating the
   unique constraint.
   ============================================================ */

SELECT
    reg_no,
    semester,
    COUNT(*) AS duplicate_count
FROM dbo.Students
GROUP BY
    reg_no,
    semester
HAVING COUNT(*) > 1;
GO


/* ============================================================
   4. FIND UNIQUE CONSTRAINTS / INDEXES ON Students
   ============================================================ */

SELECT
    i.name AS index_name,
    i.is_unique,
    i.is_primary_key,
    i.is_unique_constraint,
    c.name AS column_name
FROM sys.indexes i
INNER JOIN sys.index_columns ic
    ON i.object_id = ic.object_id
    AND i.index_id = ic.index_id
INNER JOIN sys.columns c
    ON ic.object_id = c.object_id
    AND ic.column_id = c.column_id
WHERE i.object_id = OBJECT_ID('dbo.Students')
ORDER BY
    i.name,
    ic.key_ordinal;
GO


/* ============================================================
   5. REMOVE UNIQUE CONSTRAINT/INDEX ON reg_no ONLY
   ============================================================

   The script checks indexes automatically.

   We only remove a UNIQUE index when it contains ONLY
   the reg_no column.

   We do NOT remove the primary key.
   We do NOT remove other useful indexes.
   ============================================================ */

DECLARE @IndexName NVARCHAR(128);
DECLARE @SQL NVARCHAR(MAX);

DECLARE index_cursor CURSOR LOCAL FAST_FORWARD FOR

SELECT DISTINCT
    i.name
FROM sys.indexes i
INNER JOIN sys.index_columns ic
    ON i.object_id = ic.object_id
    AND i.index_id = ic.index_id
INNER JOIN sys.columns c
    ON ic.object_id = c.object_id
    AND ic.column_id = c.column_id
WHERE i.object_id = OBJECT_ID('dbo.Students')
  AND i.is_unique = 1
  AND i.is_primary_key = 0
  AND i.is_unique_constraint = 0
  AND c.name = 'reg_no'
  AND
  (
      SELECT COUNT(*)
      FROM sys.index_columns ic2
      WHERE ic2.object_id = i.object_id
        AND ic2.index_id = i.index_id
        AND ic2.key_ordinal > 0
  ) = 1;


OPEN index_cursor;

FETCH NEXT FROM index_cursor
INTO @IndexName;

WHILE @@FETCH_STATUS = 0
BEGIN

    SET @SQL =
        N'DROP INDEX '
        + QUOTENAME(@IndexName)
        + N' ON dbo.Students;';

    PRINT 'Dropping unique index: ' + @IndexName;

    EXEC sp_executesql @SQL;

    FETCH NEXT FROM index_cursor
    INTO @IndexName;

END;

CLOSE index_cursor;
DEALLOCATE index_cursor;
GO


/* ============================================================
   6. REMOVE UNIQUE CONSTRAINT ON reg_no ONLY
   ============================================================

   If the existing unique rule was created as a
   UNIQUE CONSTRAINT, remove it.

   It is removed only when its key is exactly reg_no.
   ============================================================ */

DECLARE @ConstraintName NVARCHAR(128);
DECLARE @SQL2 NVARCHAR(MAX);

DECLARE constraint_cursor CURSOR LOCAL FAST_FORWARD FOR

SELECT DISTINCT
    kc.name
FROM sys.key_constraints kc
INNER JOIN sys.indexes i
    ON kc.parent_object_id = i.object_id
    AND kc.unique_index_id = i.index_id
INNER JOIN sys.index_columns ic
    ON i.object_id = ic.object_id
    AND i.index_id = ic.index_id
INNER JOIN sys.columns c
    ON ic.object_id = c.object_id
    AND ic.column_id = c.column_id
WHERE kc.parent_object_id = OBJECT_ID('dbo.Students')
  AND kc.type = 'UQ'
  AND c.name = 'reg_no'
  AND
  (
      SELECT COUNT(*)
      FROM sys.index_columns ic2
      WHERE ic2.object_id = i.object_id
        AND ic2.index_id = i.index_id
        AND ic2.key_ordinal > 0
  ) = 1;


OPEN constraint_cursor;

FETCH NEXT FROM constraint_cursor
INTO @ConstraintName;

WHILE @@FETCH_STATUS = 0
BEGIN

    SET @SQL2 =
        N'ALTER TABLE dbo.Students DROP CONSTRAINT '
        + QUOTENAME(@ConstraintName)
        + N';';

    PRINT 'Dropping unique constraint: ' + @ConstraintName;

    EXEC sp_executesql @SQL2;

    FETCH NEXT FROM constraint_cursor
    INTO @ConstraintName;

END;

CLOSE constraint_cursor;
DEALLOCATE constraint_cursor;
GO


/* ============================================================
   7. CHECK AGAIN FOR DUPLICATE REG_NO + SEMESTER
   ============================================================ */

SELECT
    reg_no,
    semester,
    COUNT(*) AS duplicate_count
FROM dbo.Students
GROUP BY
    reg_no,
    semester
HAVING COUNT(*) > 1;
GO


/* ============================================================
   8. CREATE UNIQUE REGISTRATION + SEMESTER RULE
   ============================================================

   This is the MOST IMPORTANT constraint.

   Same registration:
       different semester = allowed

   Same registration:
       same semester = not allowed
   ============================================================ */

IF NOT EXISTS
(
    SELECT 1
    FROM sys.key_constraints
    WHERE parent_object_id = OBJECT_ID('dbo.Students')
      AND name = 'UQ_Students_RegNo_Semester'
)
BEGIN

    ALTER TABLE dbo.Students
    ADD CONSTRAINT UQ_Students_RegNo_Semester
    UNIQUE
    (
        reg_no,
        semester
    );

    PRINT 'Unique constraint RegNo + Semester created successfully.';

END
ELSE
BEGIN

    PRINT 'UQ_Students_RegNo_Semester already exists.';

END;
GO


/* ============================================================
   9. CREATE INDEX FOR FAST REGISTRATION SEARCH
   ============================================================ */

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.Students')
      AND name = 'IX_Students_RegNo'
)
BEGIN

    CREATE INDEX IX_Students_RegNo
    ON dbo.Students(reg_no);

    PRINT 'Registration number index created.';

END;
GO


/* ============================================================
   10. CHECK StudentMarks STRUCTURE
   ============================================================ */

SELECT
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'StudentMarks'
ORDER BY ORDINAL_POSITION;
GO


/* ============================================================
   11. CHECK FOREIGN KEY
   ============================================================ */

SELECT
    fk.name AS foreign_key_name,
    OBJECT_NAME(fk.parent_object_id) AS child_table,
    COL_NAME(
        fkc.parent_object_id,
        fkc.parent_column_id
    ) AS child_column,
    OBJECT_NAME(fk.referenced_object_id) AS parent_table,
    COL_NAME(
        fkc.referenced_object_id,
        fkc.referenced_column_id
    ) AS parent_column
FROM sys.foreign_keys fk
INNER JOIN sys.foreign_key_columns fkc
    ON fk.object_id = fkc.constraint_object_id
WHERE fk.parent_object_id = OBJECT_ID('dbo.StudentMarks');
GO


/* ============================================================
   12. TEST THE FINAL STRUCTURE
   ============================================================ */

SELECT
    s.student_id,
    s.reg_no,
    s.roll_no,
    s.name,
    s.semester,
    s.program,
    COUNT(sm.mark_id) AS subject_count
FROM dbo.Students s
LEFT JOIN dbo.StudentMarks sm
    ON s.student_id = sm.student_id
GROUP BY
    s.student_id,
    s.reg_no,
    s.roll_no,
    s.name,
    s.semester,
    s.program
ORDER BY
    s.reg_no,
    s.semester;
GO


/* ============================================================
   13. TEST SAME REGISTRATION / DIFFERENT SEMESTERS
   ============================================================

   This query should show all semesters belonging to the
   same registration number.
   ============================================================ */

SELECT
    student_id,
    reg_no,
    name,
    semester
FROM dbo.Students
WHERE reg_no = 'FA22-BSCS-001'
ORDER BY semester;
GO


/* ============================================================
   FINAL DATABASE RULE

   Students:

   student_id   reg_no             semester
   ------------------------------------------------
   1            FA22-BSCS-001      Semester 1
   2            FA22-BSCS-001      Semester 2
   3            FA22-BSCS-001      Semester 3
   4            FA22-BSCS-001      Semester 4


   StudentMarks:

   student_id = 1
       -> Semester 1 subjects

   student_id = 2
       -> Semester 2 subjects

   student_id = 3
       -> Semester 3 subjects

   student_id = 4
       -> Semester 4 subjects


   Therefore your Python code can search:

       reg_no + semester

   and retrieve exactly the correct DMC.
   ============================================================ */