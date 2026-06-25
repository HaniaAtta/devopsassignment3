from flask import Flask, jsonify, request
import mysql.connector
import os
import time
from datetime import datetime

app = Flask(__name__)

# ── DB Connection ─────────────────────────────────────────
def get_db_connection():
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

# ── DB Init ───────────────────────────────────────────────
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurants (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            cuisine VARCHAR(100) NOT NULL,
            city VARCHAR(100) NOT NULL,
            rating DECIMAL(2,1) DEFAULT 0.0,
            is_open TINYINT(1) DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS menu_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            restaurant_id INT NOT NULL,
            name VARCHAR(255) NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            category VARCHAR(100) NOT NULL,
            is_available TINYINT(1) DEFAULT 1,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS riders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            phone VARCHAR(20) NOT NULL,
            city VARCHAR(100) NOT NULL,
            status VARCHAR(50) DEFAULT 'available',
            total_deliveries INT DEFAULT 0,
            rating DECIMAL(2,1) DEFAULT 5.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            customer_phone VARCHAR(20) NOT NULL,
            customer_address TEXT NOT NULL,
            restaurant_id INT NOT NULL,
            rider_id INT,
            total_amount DECIMAL(10,2) NOT NULL,
            status VARCHAR(50) DEFAULT 'pending',
            payment_method VARCHAR(50) DEFAULT 'cash',
            estimated_time INT DEFAULT 30,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id),
            FOREIGN KEY (rider_id) REFERENCES riders(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            menu_item_id INT NOT NULL,
            quantity INT NOT NULL,
            unit_price DECIMAL(10,2) NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (menu_item_id) REFERENCES menu_items(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracking_events (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            status VARCHAR(50) NOT NULL,
            message VARCHAR(255) NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    ''')

    conn.commit()
    cursor.close()
    conn.close()

# ── Health ────────────────────────────────────────────────
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'pakdeliver-api',
        'version': 'v2.0',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }), 200

# ── Restaurants ───────────────────────────────────────────
@app.route('/api/restaurants', methods=['GET'])
def get_restaurants():
    city = request.args.get('city')
    cuisine = request.args.get('cuisine')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = 'SELECT * FROM restaurants WHERE 1=1'
    params = []
    if city:
        query += ' AND city = %s'
        params.append(city)
    if cuisine:
        query += ' AND cuisine = %s'
        params.append(cuisine)
    query += ' ORDER BY rating DESC'
    cursor.execute(query, params)
    restaurants = cursor.fetchall()
    cursor.close()
    conn.close()
    for r in restaurants:
        r['rating'] = float(r['rating'])
        r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    return jsonify({'restaurants': restaurants, 'total': len(restaurants)}), 200

@app.route('/api/restaurants', methods=['POST'])
def add_restaurant():
    data = request.get_json()
    required = ['name', 'cuisine', 'city']
    if not data or any(k not in data for k in required):
        return jsonify({'error': 'name, cuisine, city required'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO restaurants (name, cuisine, city, rating) VALUES (%s, %s, %s, %s)',
        (data['name'], data['cuisine'], data['city'], data.get('rating', 4.0))
    )
    conn.commit()
    rid = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({'id': rid, 'name': data['name'], 'message': 'Restaurant added'}), 201

# ── Menu ──────────────────────────────────────────────────
@app.route('/api/restaurants/<int:restaurant_id>/menu', methods=['GET'])
def get_menu(restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM menu_items WHERE restaurant_id = %s AND is_available = 1', (restaurant_id,))
    items = cursor.fetchall()
    cursor.close()
    conn.close()
    for item in items:
        item['price'] = float(item['price'])
    return jsonify({'menu': items, 'total': len(items)}), 200

@app.route('/api/restaurants/<int:restaurant_id>/menu', methods=['POST'])
def add_menu_item(restaurant_id):
    data = request.get_json()
    required = ['name', 'price', 'category']
    if not data or any(k not in data for k in required):
        return jsonify({'error': 'name, price, category required'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO menu_items (restaurant_id, name, price, category) VALUES (%s, %s, %s, %s)',
        (restaurant_id, data['name'], data['price'], data['category'])
    )
    conn.commit()
    mid = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({'id': mid, 'name': data['name'], 'message': 'Menu item added'}), 201

# ── Riders ────────────────────────────────────────────────
@app.route('/api/riders', methods=['GET'])
def get_riders():
    status = request.args.get('status')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if status:
        cursor.execute('SELECT * FROM riders WHERE status = %s', (status,))
    else:
        cursor.execute('SELECT * FROM riders ORDER BY rating DESC')
    riders = cursor.fetchall()
    cursor.close()
    conn.close()
    for r in riders:
        r['rating'] = float(r['rating'])
        r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    return jsonify({'riders': riders, 'total': len(riders)}), 200

@app.route('/api/riders', methods=['POST'])
def add_rider():
    data = request.get_json()
    required = ['name', 'phone', 'city']
    if not data or any(k not in data for k in required):
        return jsonify({'error': 'name, phone, city required'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO riders (name, phone, city) VALUES (%s, %s, %s)',
        (data['name'], data['phone'], data['city'])
    )
    conn.commit()
    rid = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({'id': rid, 'name': data['name'], 'message': 'Rider registered'}), 201

@app.route('/api/riders/<int:rider_id>/status', methods=['PUT'])
def update_rider_status(rider_id):
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'error': 'status required'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE riders SET status = %s WHERE id = %s', (data['status'], rider_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': f'Rider {rider_id} status updated to {data["status"]}'}), 200

# ── Orders ────────────────────────────────────────────────
@app.route('/api/orders', methods=['POST'])
def place_order():
    data = request.get_json()
    required = ['customer_name', 'customer_phone', 'customer_address', 'restaurant_id', 'items', 'payment_method']
    if not data or any(k not in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # auto-assign available rider
    cursor.execute('SELECT id FROM riders WHERE status = %s LIMIT 1', ('available',))
    rider = cursor.fetchone()
    rider_id = rider['id'] if rider else None

    # calculate total
    total = 0
    for item in data['items']:
        cursor.execute('SELECT price FROM menu_items WHERE id = %s', (item['menu_item_id'],))
        menu_item = cursor.fetchone()
        if menu_item:
            total += float(menu_item['price']) * item['quantity']

    cursor2 = conn.cursor()
    cursor2.execute('''
        INSERT INTO orders (customer_name, customer_phone, customer_address,
                           restaurant_id, rider_id, total_amount, payment_method)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', (data['customer_name'], data['customer_phone'], data['customer_address'],
          data['restaurant_id'], rider_id, total, data['payment_method']))
    conn.commit()
    order_id = cursor2.lastrowid

    # insert order items
    for item in data['items']:
        cursor2.execute('SELECT price FROM menu_items WHERE id = %s', (item['menu_item_id'],))
        menu_item = cursor2.fetchone()
        if menu_item:
            cursor2.execute(
                'INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price) VALUES (%s, %s, %s, %s)',
                (order_id, item['menu_item_id'], item['quantity'], menu_item[0])
            )

    # mark rider busy
    if rider_id:
        cursor2.execute('UPDATE riders SET status = %s WHERE id = %s', ('busy', rider_id))

    # initial tracking event
    cursor2.execute(
        'INSERT INTO tracking_events (order_id, status, message) VALUES (%s, %s, %s)',
        (order_id, 'pending', 'Order received and being confirmed by restaurant')
    )
    conn.commit()
    cursor.close()
    cursor2.close()
    conn.close()

    return jsonify({
        'order_id': order_id,
        'total_amount': total,
        'rider_assigned': rider_id is not None,
        'estimated_time': '30 minutes',
        'message': 'Order placed successfully'
    }), 201

@app.route('/api/orders', methods=['GET'])
def get_orders():
    status = request.args.get('status')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if status:
        cursor.execute('''
            SELECT o.id, o.customer_name, o.customer_phone, o.customer_address,
                   r.name as restaurant_name, ri.name as rider_name,
                   o.total_amount, o.status, o.payment_method, o.created_at
            FROM orders o
            JOIN restaurants r ON o.restaurant_id = r.id
            LEFT JOIN riders ri ON o.rider_id = ri.id
            WHERE o.status = %s ORDER BY o.created_at DESC
        ''', (status,))
    else:
        cursor.execute('''
            SELECT o.id, o.customer_name, o.customer_phone, o.customer_address,
                   r.name as restaurant_name, ri.name as rider_name,
                   o.total_amount, o.status, o.payment_method, o.created_at
            FROM orders o
            JOIN restaurants r ON o.restaurant_id = r.id
            LEFT JOIN riders ri ON o.rider_id = ri.id
            ORDER BY o.created_at DESC
        ''')
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    for o in orders:
        o['total_amount'] = float(o['total_amount'])
        o['created_at'] = o['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    return jsonify({'orders': orders, 'total': len(orders)}), 200

@app.route('/api/orders/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'error': 'status required'}), 400

    status = data['status']
    valid = ['pending', 'confirmed', 'preparing', 'picked_up', 'on_the_way', 'delivered', 'cancelled']
    if status not in valid:
        return jsonify({'error': f'status must be one of {valid}'}), 400

    messages = {
        'confirmed': 'Restaurant has confirmed your order',
        'preparing': 'Your food is being prepared',
        'picked_up': 'Rider has picked up your order',
        'on_the_way': 'Your order is on the way!',
        'delivered': 'Order delivered successfully',
        'cancelled': 'Order has been cancelled'
    }

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT rider_id FROM orders WHERE id = %s', (order_id,))
    order = cursor.fetchone()

    cursor2 = conn.cursor()
    cursor2.execute('UPDATE orders SET status = %s WHERE id = %s', (status, order_id))
    cursor2.execute(
        'INSERT INTO tracking_events (order_id, status, message) VALUES (%s, %s, %s)',
        (order_id, status, messages.get(status, f'Status updated to {status}'))
    )

    # free up rider when delivered/cancelled
    if status in ('delivered', 'cancelled') and order and order['rider_id']:
        cursor2.execute('UPDATE riders SET status = %s, total_deliveries = total_deliveries + 1 WHERE id = %s',
                       ('available', order['rider_id']))

    conn.commit()
    cursor.close()
    cursor2.close()
    conn.close()
    return jsonify({'order_id': order_id, 'status': status, 'message': messages.get(status, 'Updated')}), 200

# ── Tracking ──────────────────────────────────────────────
@app.route('/api/orders/<int:order_id>/tracking', methods=['GET'])
def get_tracking(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT o.id, o.customer_name, o.status as current_status,
               o.total_amount, r.name as restaurant_name,
               ri.name as rider_name, ri.phone as rider_phone, o.estimated_time
        FROM orders o
        JOIN restaurants r ON o.restaurant_id = r.id
        LEFT JOIN riders ri ON o.rider_id = ri.id
        WHERE o.id = %s
    ''', (order_id,))
    order = cursor.fetchone()
    if not order:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Order not found'}), 404

    cursor.execute('SELECT status, message, timestamp FROM tracking_events WHERE order_id = %s ORDER BY timestamp ASC', (order_id,))
    events = cursor.fetchall()
    cursor.close()
    conn.close()

    order['total_amount'] = float(order['total_amount'])
    for e in events:
        e['timestamp'] = e['timestamp'].strftime('%Y-%m-%d %H:%M:%S')

    return jsonify({'order': order, 'tracking_history': events}), 200

# ── Dashboard ─────────────────────────────────────────────
@app.route('/api/dashboard', methods=['GET'])
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute('SELECT COUNT(*) as total FROM orders')
    total_orders = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM orders WHERE status = %s', ('pending',))
    pending = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM orders WHERE status = %s', ('delivered',))
    delivered = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM orders WHERE status = %s', ('cancelled',))
    cancelled = cursor.fetchone()['total']

    cursor.execute('SELECT COALESCE(SUM(total_amount), 0) as revenue FROM orders WHERE status = %s', ('delivered',))
    revenue = float(cursor.fetchone()['revenue'])

    cursor.execute('SELECT COUNT(*) as total FROM riders WHERE status = %s', ('available',))
    available_riders = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM restaurants WHERE is_open = 1')
    active_restaurants = cursor.fetchone()['total']

    cursor.execute('''
        SELECT r.name, COUNT(o.id) as order_count
        FROM restaurants r LEFT JOIN orders o ON r.id = o.restaurant_id
        GROUP BY r.id, r.name ORDER BY order_count DESC LIMIT 3
    ''')
    top_restaurants = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({
        'summary': {
            'total_orders': total_orders,
            'pending_orders': pending,
            'delivered_orders': delivered,
            'cancelled_orders': cancelled,
            'total_revenue_pkr': revenue,
            'available_riders': available_riders,
            'active_restaurants': active_restaurants
        },
        'top_restaurants': top_restaurants
    }), 200





# ── Ratings ───────────────────────────────────────────────
@app.route('/api/orders/<int:order_id>/rate', methods=['POST'])
def rate_order(order_id):
    data = request.get_json()
    if not data or 'rating' not in data:
        return jsonify({'error': 'rating required (1-5)'}), 400
    rating = float(data['rating'])
    if rating < 1 or rating > 5:
        return jsonify({'error': 'rating must be between 1 and 5'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT rider_id, status FROM orders WHERE id = %s', (order_id,))
    order = cursor.fetchone()
    if not order:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Order not found'}), 404
    if order['status'] != 'delivered':
        cursor.close()
        conn.close()
        return jsonify({'error': 'Can only rate delivered orders'}), 400
    cursor2 = conn.cursor()
    if order['rider_id']:
        cursor2.execute('''
            UPDATE riders SET rating = ROUND((rating + %s) / 2, 1)
            WHERE id = %s
        ''', (rating, order['rider_id']))
    cursor2.execute(
        'INSERT INTO tracking_events (order_id, status, message) VALUES (%s, %s, %s)',
        (order_id, 'rated', f'Customer rated the order {rating}/5')
    )
    conn.commit()
    cursor.close()
    cursor2.close()
    conn.close()
    return jsonify({'message': f'Order rated {rating}/5 successfully', 'order_id': order_id}), 200

# ── Rider Leaderboard ─────────────────────────────────────
@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT name, city, total_deliveries, rating, status
        FROM riders
        ORDER BY total_deliveries DESC, rating DESC
        LIMIT 10
    ''')
    riders = cursor.fetchall()
    cursor.close()
    conn.close()
    for r in riders:
        r['rating'] = float(r['rating'])
    return jsonify({'leaderboard': riders, 'total_riders': len(riders)}), 200

# ── Search ────────────────────────────────────────────────
@app.route('/api/search', methods=['GET'])
def search():
    city = request.args.get('city', '')
    cuisine = request.args.get('cuisine', '')
    min_rating = request.args.get('min_rating', 0)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT r.id, r.name, r.cuisine, r.city, r.rating,
               COUNT(m.id) as menu_items_count
        FROM restaurants r
        LEFT JOIN menu_items m ON r.id = m.restaurant_id
        WHERE r.city LIKE %s
        AND r.cuisine LIKE %s
        AND r.rating >= %s
        AND r.is_open = 1
        GROUP BY r.id
        ORDER BY r.rating DESC
    ''', (f'%{city}%', f'%{cuisine}%', min_rating))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    for r in results:
        r['rating'] = float(r['rating'])
    return jsonify({'results': results, 'total_found': len(results)}), 200

# ── Order Analytics ───────────────────────────────────────
@app.route('/api/analytics', methods=['GET'])
def analytics():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT
            COUNT(*) as total_orders,
            COALESCE(SUM(total_amount), 0) as total_revenue,
            COALESCE(AVG(total_amount), 0) as avg_order_value,
            COUNT(CASE WHEN status = 'delivered' THEN 1 END) as delivered,
            COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
            COUNT(CASE WHEN payment_method = 'cash' THEN 1 END) as cash_orders,
            COUNT(CASE WHEN payment_method = 'card' THEN 1 END) as card_orders
        FROM orders
    ''')
    stats = cursor.fetchone()
    cursor.execute('''
        SELECT DATE(created_at) as date, COUNT(*) as orders,
               COALESCE(SUM(total_amount), 0) as revenue
        FROM orders
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        LIMIT 7
    ''')
    daily = cursor.fetchall()
    cursor.close()
    conn.close()
    stats['total_revenue'] = float(stats['total_revenue'])
    stats['avg_order_value'] = float(stats['avg_order_value'])
    for d in daily:
        d['revenue'] = float(d['revenue'])
        d['date'] = str(d['date'])
    return jsonify({'overall_stats': stats, 'daily_breakdown': daily}), 200

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
