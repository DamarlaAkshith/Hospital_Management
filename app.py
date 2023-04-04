from flask import Flask, request, jsonify
from datetime import datetime
from con import set_connection
from loggerinstance import logger

app = Flask(__name__)


# CREATE TABLE patients (
#     id SERIAL PRIMARY KEY,
#     name VARCHAR(255) NOT NULL,
#     dob DATE NOT NULL,
#     gender VARCHAR(10) NOT NULL,
#     admit_date DATE NOT NULL,
#     discharge_date DATE
# );
#
# CREATE TABLE treatments (
#     id SERIAL PRIMARY KEY,
#     patient_id INTEGER NOT NULL REFERENCES patients(id),
#     treatment_name VARCHAR(255) NOT NULL,
#     treatment_date DATE NOT NULL
# );
#
# CREATE TABLE admissions (
#     id SERIAL PRIMARY KEY,
#     patient_id INTEGER NOT NULL REFERENCES patients(id),
#     admission_date DATE NOT NULL,
#     discharge_date DATE,
#     diagnosis VARCHAR(255)
# );
#
def handle_exceptions(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except psycopg2.Error as e:
            conn = kwargs.get('conn')
            if conn:
                conn.rollback()
            logger.error(str(e))
            return jsonify({"error": "Database error"})
        except Exception as e:
            logger.error(str(e))
            return jsonify({"error": "Internal server error"})

    return wrapper


# Define the routes for patient management

@app.route('/v1/admit', methods=['POST'])
@handle_exceptions
def admit_patient():
    # {
    #     "patient_name": "John",
    #     "dob": "1990-01-01",
    #     "gender": "M",
    #     "admit_date": "2023-03-26"
    # }

    data = request.get_json()
    patient_name = data['patient_name']
    dob = datetime.strptime(data['dob'], '%Y-%m-%d').date()
    gender = data['gender']
    admit_date = datetime.strptime(data['admit_date'], '%Y-%m-%d').date()
    discharge_date = None
    cur, conn = set_connection()
    cur.execute(
        "INSERT INTO patients (name, dob, gender, admit_date, discharge_date) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (patient_name, dob, gender, admit_date, discharge_date)
    )

    patient_id = cur.fetchone()[0]
    conn.commit()
    logger.info(f"Patient admitted - Name: {patient_name}, DOB: {dob}, Gender: {gender}, Admit date: {admit_date}")

    return jsonify({"patient_id": patient_id, "message": "Patient admitted successfully"})


@app.route('/v1/admissions', methods=['GET'], endpoint='get_admissions')
@handle_exceptions
def get_admissions():
    cur, conn = set_connection()
    cur.execute("SELECT * FROM patients WHERE discharge_date IS NULL")
    patients = cur.fetchall()
    admissions = []
    for patient in patients:
        admission = {
            "patient_id": patient[0],
            "patient_name": patient[1],
            "dob": str(patient[2]),
            "gender": patient[3],
            "admit_date": str(patient[4])
        }

        admissions.append(admission)
    logger.info(f"Retrieved admissions data for {len(admissions)} patients")
    return jsonify(admissions)


@app.route('/v1/treatments', methods=['POST'], endpoint='add_treatment')
@handle_exceptions
def add_treatment():
    # {
    #     "patient_id": 1,
    #     "treatment_name": "X-ray",
    #     "treatment_date": "2023-03-27"
    # }

    data = request.get_json()
    patient_id = data['patient_id']
    treatment_name = data['treatment_name']
    treatment_date = datetime.strptime(data['treatment_date'], '%Y-%m-%d').date()
    cur, conn = set_connection()
    cur.execute("SELECT * FROM patients WHERE id = %s AND discharge_date IS NULL", (patient_id,))
    patient = cur.fetchone()
    if patient:
        cur.execute(
            "INSERT INTO treatments "
            "(patient_id, treatment_name, treatment_date) "
            "VALUES (%s, %s, %s)",
            (patient_id, treatment_name, treatment_date)
        )

        conn.commit()
        logger.info(f"Treatment {treatment_name} added for patient with ID {patient_id}")
        return jsonify({"message": "Treatment added successfully"})
    else:
        return jsonify("Patient record not found")


@app.route('/v1/patients/discharge', methods=['PUT'], endpoint='discharge_patient')
@handle_exceptions
def discharge_patient():
    # {
    #     "patient_id": 1,
    #     "discharge_date": "2023-03-28",
    #     "diagnosis": "Fractured leg"
    # }

    data = request.get_json()
    patient_id = data['patient_id']
    discharge_date = data['discharge_date']
    diagnosis = data['diagnosis']
    cur, conn = set_connection()
    cur.execute("SELECT * FROM admissions WHERE patient_id = %s AND discharge_date IS NULL", (patient_id,))
    admission = cur.fetchone()
    if admission:
        cur.execute("UPDATE admissions SET discharge_date = %s, diagnosis = %s WHERE id = %s",
                    (discharge_date, diagnosis, admission[0]))
        conn.commit()
        logger.info(f"Patient with id {patient_id} discharged successfully")
        return jsonify({"message": "Patient discharged successfully"})
    else:
        logger.error(f"Patient with id {patient_id} not currently admitted")
        return jsonify("Patient not currently admitted")


@app.route('/v1/patients/<int:patient_id>', methods=['GET'], endpoint='get_patient_by_id')
@handle_exceptions
def get_patient_by_id(patient_id):
    cur, conn = set_connection()
    cur.execute("SELECT * FROM patients WHERE id = %s", (patient_id,))
    patient = cur.fetchone()
    if patient:
        cur.execute("SELECT * FROM admissions WHERE patient_id = %s ORDER BY admission_date DESC", (patient_id,))
        admissions = cur.fetchall()
        patient_record = {"id": patient[0], "name": patient[1], "dob": patient[2], "admissions": []}
        for admission in admissions:
            admission_record = {"id": admission[0], "admission_date": admission[2], "discharge_date": admission[3],
                                "diagnosis": admission[4]}
            patient_record["admissions"].append(admission_record)
            logger.info(f"Patient with id {patient_id} found and retrieved successfully")
        return jsonify(patient_record)
    else:
        logger.error(f"Patient with id {patient_id} not found")
        return jsonify("Patient not found")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
