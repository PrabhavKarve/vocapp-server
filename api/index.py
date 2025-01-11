from flask import Flask, request, jsonify
from flask_cors import CORS
from psycopg2.extras import RealDictCursor
from flask_bcrypt import Bcrypt
import psycopg2
from dotenv import load_dotenv
import os
import random

load_dotenv()

# Database configuration from environment variables
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
app = Flask(__name__)
bcrypt = Bcrypt(app)
CORS(app)  # Enable CORS to allow requests from the React frontend

@app.route('/api/message', methods=['POST'])
def process_message():
    data = request.get_json()
    user_message = data.get('message', '')
    response_message = f"Server received: {user_message}"

    return jsonify({'response': response_message})

@app.route('/', methods=['GET'])
def hello():
    try:

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.close()
        conn.close()
        return jsonify("server live")
    except Exception as e:
        return f"Error: {e}"

def insert_all_word_ids_for_user(email, conn):
    cursor = conn.cursor()
    try:
        for level in range(1, 35):  # Levels from 1 to 34
            table_name = f"flashcardsLevel_{level}"
            query = f"SELECT wordId, word FROM {table_name};"
            cursor.execute(query)
            word_ids = cursor.fetchall()
            for word_id in word_ids:
                insert_query = """
                INSERT INTO user_to_word (user_id, level_id, word_id, frequency)
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(insert_query, (email, level, word_id[0], 0))

        conn.commit()

    except Exception as e:
        print(f"Error inserting wordIds for user {email}: {e}")
        conn.rollback()

    finally:
        # Close the database connection
        cursor.close()
        conn.close()

# Connect to PostgreSQL
def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        port="5432",
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn

# Signup endpoint
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data['email']
    firstname = data['firstName']
    lastname = data['lastName']
    password = data['password']
    confirm_password = data['confirmPassword']

    # Check if password and confirm password match
    if password != confirm_password:
        return jsonify({"error": "Passwords do not match"}), 400

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Insert user data into database
        cursor.execute(
            "INSERT INTO users (email, firstname, lastname, password) VALUES (%s, %s, %s, %s)",
            (email, firstname, lastname, password)
        )
        conn.commit()
        insert_all_word_ids_for_user(email, conn)


        cursor.close()
        conn.close()
        return jsonify({"message": "User registered successfully"}), 201

    except psycopg2.IntegrityError:
        return jsonify({"error": "Email already exists"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Login endpoint
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data['email']
    password = data['password']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:  # Assuming password check is not yet implemented
            # Return user details with the response
            return jsonify({"message": "Login successful", "user": user['firstname']}), 200
        else:
            return jsonify({"message": "Invalid email or password"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/getFlashcards_level_n', methods=['POST'])
def handle_post_request():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        data = request.get_json()
        level_id = data.get('levelId')
        table_name = f"flashcardslevel_{level_id}"
        query = f"SELECT * FROM {table_name}"
        cursor.execute(query)
        results  = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'data': results}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Something went wrong"}), 500

@app.route('/getMasteredCount', methods=['POST'])
def getMasteredCount():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        data = request.get_json()
        wordUserId = data.get('userEmail')
        wordLevelId = data.get('levelId')
        query = """select count(*) from user_to_word where user_id = %s and level_id = %s and status = 'Mastered';"""
        params = (wordUserId, wordLevelId)
        cursor.execute(query, params)
        count = cursor.fetchone()['count']
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'mastered_count': count}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Something went wrong"}), 500

@app.route('/isKnown', methods=['POST'])
def handleIsKnown():
    data = request.get_json()
    word = data.get("word")
    wordId = data.get("wordId")
    wordLevelId = data.get("wordLevelId")
    wordUserId = data.get("wordUserId")  # User's email or ID
    isKnown = data.get("isKnown")

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    query_1 = """
    SELECT * FROM user_to_word uw JOIN users u ON uw.user_id = u.email WHERE email = %s and level_id = %s and word_id = %s;
    """
    cursor.execute(query_1, (wordUserId, wordLevelId, wordId ))
    result_1 = cursor.fetchone()
    current_frequency = result_1['frequency']
    current_status = result_1['status']

    new_frequency = 0
    new_status = ""

    if isKnown == "known":
        if current_frequency == 10:
            new_frequency = 10
            new_status = "Mastered"
        else:
            if current_frequency < 5:
                new_frequency = current_frequency + 1
                new_status = "learning"
            else:
                new_frequency = current_frequency + 1
                new_status = "Mastered"

    elif isKnown == "unknown":
        if current_frequency == 0:
            new_frequency = 0
            new_status = "learning"
        else:
            if current_frequency <= 5:
                new_frequency = current_frequency - 1
                new_status = "learning"
            else:
                new_frequency = current_frequency - 1
                new_status = "Mastered"

    update_query = """
    UPDATE user_to_word 
    SET frequency = %s, status = %s 
    WHERE user_id = %s AND word_id = %s AND level_id = %s
    """
    params = (new_frequency, new_status, wordUserId, wordId, wordLevelId)
    cursor.execute(update_query, params)
    conn.commit()

    query = """select count(*) from user_to_word where user_id = %s and level_id = %s and status = 'Mastered';"""
    params = (wordUserId, wordLevelId)
    cursor.execute(query, params)
    count = cursor.fetchone()['count']
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"mastered_count": count}), 200


@app.route('/reviews', methods=['POST'])
def add_review():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    reviews = []
    data = request.json
    stars = data.get('stars')
    description = data.get('description')
    full_name = data.get('full_name')
    country = data.get('country')
    city = data.get('city')

    if not stars or not description or not full_name or not country or not city:
        return jsonify({"message": "Stars, description, full name, country, and city are required."}), 400

    try:
        cursor.execute(
            "INSERT INTO reviews (stars, description, full_name, country, city) VALUES (%s, %s, %s, %s, %s);",
            (stars, description, full_name, country, city)
        )
        conn.commit()

        cursor.execute("SELECT id, stars, description, full_name, country, city, created_at FROM reviews;")
        rows = cursor.fetchall()

        reviews = [
            {
                "id": i.get('id'),
                "stars": i.get('stars'),
                "description": i.get('description'),
                "full_name": i.get('full_name'),
                "country": i.get('country'),
                "city": i.get('city'),
                "created_at": i.get('created_at')
            }
            for i in rows
        ]

        return jsonify({"reviews": reviews}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/getReviews', methods=['GET'])
def get_reviews():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT id, stars, description, full_name, country, city, created_at FROM reviews;")
        rows = cursor.fetchall()

        reviews = [
            {
                "id": i.get('id'),
                "stars": i.get('stars'),
                "description": i.get('description'),
                "full_name": i.get('full_name'),
                "country": i.get('country'),
                "city": i.get('city'),
                "created_at": str(i.get('created_at'))  # Ensure it is a string
            }
            for i in rows
        ]
        return jsonify({"reviews": reviews}), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/getquestions', methods=['POST'])
def get_questions():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    data = request.json
    no_of_questions = data.get('no_of_questions')  # Default to 10 questions if not provided
    level_id = data.get('level_id')
    # Query to get all words and meanings
    table_name = f"flashcardslevel_{level_id}"
    query = f"SELECT word, meaning FROM {table_name}"
    cursor.execute(query)
    all_data = cursor.fetchall()

    if len(all_data) < no_of_questions:
        return {"error": "Not enough data in the table to generate questions."}, 400

    # Select `no_of_questions` unique words for questions
    question_data = random.sample(all_data, no_of_questions)

    questions = []
    for entry in question_data:
        correct_meaning = entry['meaning']
        word = entry['word']

        # Generate 3 incorrect meanings by sampling from the rest of the meanings
        remaining_meanings = [item['meaning'] for item in all_data if item['meaning'] != correct_meaning]
        incorrect_meanings = random.sample(remaining_meanings, 3)

        # Combine the correct meaning with the incorrect ones and shuffle
        choices = incorrect_meanings + [correct_meaning]
        random.shuffle(choices)

        # Add question with word and shuffled choices
        questions.append({
            "word": word,
            "choices": choices,
            "answer": correct_meaning  # To validate the correct answer if needed
        })

    return {"questions": questions}

@app.route('/putTestScores', methods=['POST'])
def getuserTestScore():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        data = request.json
        userid = data.get('userid')
        level_id = data.get('level_id')  # Assuming level_id corresponds to the "level" column
        score = data.get('score')
        print(userid, level_id, score)
        # SQL query to insert a record into the testScores table
        insert_query = """
            INSERT INTO testScores (userId, score, levelid)
            VALUES (%s, %s, %s)
            RETURNING *;
            """
        cursor.execute(insert_query, (userid, score, level_id))
        conn.commit()

        # Fetch the inserted row
        inserted_row = cursor.fetchone()

        return jsonify({"status": "success", "data": inserted_row}), 201

    except Exception as e:
        conn.rollback()  # Rollback in case of error
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
