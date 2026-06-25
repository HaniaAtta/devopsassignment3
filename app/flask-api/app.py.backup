from flask import Flask, jsonify, request
import mysql.connector
import os
import time

app = Flask(__name__)

def get_db_connection():
    """Create database connection using environment variables."""
    max_retries = 30
    for i in range(max_retries):
        try:
            conn = mysql.connector.connect(
                host=os.environ.get('DB_HOST', 'mysql'),
                user=os.environ.get('DB_USER', 'flaskuser'),
                password=os.environ.get('DB_PASSWORD', 'flaskpass'),
                database=os.environ.get('DB_NAME', 'flaskdb')
            )
            return conn
        except mysql.connector.Error:
            if i < max_retries - 1:
                time.sleep(2)
            else:
                raise

def init_db():
    """Initialize the database table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'service': 'flask-api'}), 200

@app.route('/api/items', methods=['GET'])
def get_items():
    """Get all items."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM items ORDER BY created_at DESC')
    items = cursor.fetchall()
    cursor.close()
    conn.close()
    for item in items:
        item['created_at'] = item['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    return jsonify(items), 200

@app.route('/api/items', methods=['POST'])
def create_item():
    """Create a new item."""
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Name is required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO items (name, description) VALUES (%s, %s)',
        (data['name'], data.get('description', ''))
    )
    conn.commit()
    item_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({'id': item_id, 'name': data['name'], 'description': data.get('description', '')}), 201

@app.route('/api/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    """Delete an item."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM items WHERE id = %s', (item_id,))
    conn.commit()
    affected = cursor.rowcount
    cursor.close()
    conn.close()
    if affected == 0:
        return jsonify({'error': 'Item not found'}), 404
    return jsonify({'message': 'Item deleted'}), 200

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
