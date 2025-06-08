import eventlet
eventlet.monkey_patch()


from flask import Flask, render_template, request, redirect, url_for, session, make_response, jsonify
import api
import datetime
from flask_caching import Cache
import requests
import googlemaps
import os
import uuid
from PIL import Image, UnidentifiedImageError
import random
from asgiref.wsgi import WsgiToAsgi
import razorpay
import re
from urllib.parse import quote
import threading
from concurrent.futures import ThreadPoolExecutor
from google import genai
from google.genai import types
import uuid
import urllib3

# Disable SSL warnings (for testing only, not recommended for production)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Ensure you use a secure key for session
app.config['SESSION_PERMANENT'] = True  # Make session persistent
app.config['SESSION_TYPE'] = 'filesystem'  # Store session on server

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
# app.config['SESSION_TYPE'] = 'redis'
# app.config['SESSION_PERMANENT'] = False
# Session(app)


# # Configure Flask-Caching with Redis
# app.config['CACHE_TYPE'] = 'redis'
# app.config['CACHE_REDIS_HOST'] = 'localhost'
# app.config['CACHE_REDIS_PORT'] = 6379
# cache = Cache(app)

GOOGLE_MAPS_API_KEY = "AIzaSyCdc5N7AzzvPiWddsegRCRmna3LxG5HCmk"
razorpay_client = razorpay.Client(auth=("rzp_test_SWjvcpME4fGCmq", "ZuTowFTbz7voWmL6VmstfMgc"))


# Upload folder configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)



@app.route("/")
def index():
    username = request.cookies.get('username')
    
    if username:
        session['username'] = username

        return redirect(url_for('dashboard'))
        
    else:
        return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    username = request.cookies.get('username')
    # print(username)
    # if username:
    #     session['username'] = username
    #     return redirect(url_for('main'))

    if request.method == 'POST':
        username = request.form['number']
        password = request.form['password']

        print(username, password)

        checklogin = api.login(username, password)
        print(checklogin)

        if checklogin:
            session.clear()  # Clear previous session data
            session['username'] = username
            expire_date = datetime.datetime.now() + datetime.timedelta(days=30)
            resp = make_response(redirect(url_for('dashboard')))
            resp.set_cookie('username', username, expires=expire_date)
            return resp
        else:
            error = "Invalid login credentials!"
            return render_template('login.html', error=error)
        
    return render_template('login.html')


@app.route("/signup", methods=['POST', 'GET'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')

        print("Signup Creds ", name, email, phone, password)

        checkuser = api.checkuser(email, phone)

        if checkuser == False:
            otp = random.randint(1000, 9999)
            
            session['otp'] = otp

            print("Otp ", otp)

            session['signup_info'] = {'name': name, 'email': email, 'phone': phone, 'password': password}

            # Threaded call to send_mail
            threading.Thread(target=api.send_mail, args=(email, otp)).start()

            return redirect(url_for('otp_verification'))
        else:
            return render_template("signup.html", error = "User already exist!")
    else:
        return render_template("signup.html")


@app.route("/otp_verification", methods=['GET', 'POST'])
def otp_verification():
    if request.method == 'POST':
        user_info = session.get('signup_info')
        email = session.get('signup_info', {}).get('email', None)
        entered_otp = request.form.get('otp')
        ip_address = request.form.get('ip_address')

        stored_otp = str(session.get('otp'))  # Ensure both are strings

        print("ip_address: ", ip_address)

        if entered_otp == stored_otp:

            def threaded_send_otp(name, email, number, password, ip_address):
                status = api.signup(name, email, number, password, ip_address)
                print("OTP Status (in thread):", status)

            thread = threading.Thread(
                target=threaded_send_otp,
                args=(user_info.get("name"), user_info.get("email"), user_info.get("phone"), user_info.get("password"), ip_address)
            )
            thread.start()
            
            return redirect(url_for('dashboard'))  # Update as needed

        else:
            return render_template("otp_verification.html", error="Enter valid OTP")
        
    else:
        # ✅ Return this for GET requests
        email = session.get('signup_info', {}).get('email', None)
        return render_template("otp_verification.html", email=email)

@app.route("/dashboard")
def dashboard():
    buttons = [
        {"text": "B&W", "image": "b-w.jpeg"},
        {"text": "DENON", "image": "denon.jpeg"},
        {"text": "MARANTZ", "image": "marantz.jpeg"},
        {"text": "JBL", "image": "jbl.svg"},
        {"text": "DALI", "image": "dali.png"},
        {"text": "KRIX", "image": "krix.png"},
        {"text": "KLIPSCH", "image": "klipsch.jpeg"},
        {"text": "FOCAL", "image": "focal.jpeg"}
    ]

    # Fetch products from your API
    fetch_product = api.fetch_products()
    print("fetch_product", fetch_product)

    # Function to process each product
    def process_product(item):
        try:
            name = item[0]
            brand = item[1]
            product_id = item[2]
            price = item[3]
            image_string = item[4]
            all_image = image_string.split(',')
            return {
                "brand": brand,
                "name": name,
                "price": price,
                "image": all_image[0].strip() if all_image else "default.webp",
                "product_id": str(product_id)
            }
        except Exception as e:
            print(f"Error processing item: {item} - {e}")
            return None

    # Use ThreadPoolExecutor to process products in parallel
    products = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(process_product, fetch_product)
        products = [p for p in results if p is not None]

    return render_template("dashboard.html", buttons=buttons, products=products)
    

@app.route("/profile")
def profile():
    username = request.cookies.get('username')

    print("username ", username)

    def fetch_data(username):
        return api.fetch_profile(username)

    # Use ThreadPoolExecutor to get return value
    with ThreadPoolExecutor() as executor:
        future = executor.submit(fetch_data, username)
        profile_details = future.result()  # Wait for result

    return render_template("profile.html", name=profile_details[0], email=profile_details[2])


@app.route('/contactus', methods=['GET', 'POST'])
def contactus():
    if request.method == 'POST':
        # Get required data from request
        username = request.cookies.get('username')
        data = request.get_json()
        name = data.get('name')
        number = data.get('number')
        message = data.get('message')

        if not name or not number or not message:
            return jsonify({'success': False, 'error': 'All fields are required'}), 400

        # Define the background function with arguments
        def process_ticket(username, name, number, message):
            print(f"Ticket raised by {name}, Number: {number}, Message: {message}")
            try:
                api.contactus(username, name, number, message)
            except Exception as e:
                print("Error in ticket processing:", e)

        # Start the thread safely
        thread = threading.Thread(target=process_ticket, args=(username, name, number, message))
        thread.start()

        return jsonify({'success': True})

    return render_template('contactus.html')


@app.route("/product_details/<product_id>")
def product_details(product_id):
    print("product_id", product_id)

    # Use thread pool to fetch product & bid data concurrently
    with ThreadPoolExecutor() as executor:
        futures = {
            'product': executor.submit(api.fetch_product_details, product_id, user_id="999"),
            'bids': executor.submit(api.fetch_bids_details, product_id),
            'competitors': executor.submit(api.fetch_competitors, product_id)
        }

        fetch_product = futures['product'].result()
        fetch_bids = futures['bids'].result()
        raw_competitor = futures['competitors'].result()

        competitors = [raw_competitor] if isinstance(raw_competitor, dict) else (raw_competitor or [])

        print("competitors ", competitors)


    if fetch_product and isinstance(fetch_product, tuple):
        product_data, fav_data = fetch_product
        name = product_data.get("name", "")
        brand = product_data.get("brand", "")
        description = product_data.get("description", "")
        db_product_id = product_data.get("product_id", "")
        
        # Parse and sanitize price
        try:
            current_price = int(product_data.get("current_price", 0))
            base_price = int(product_data.get("price", 0))
            price = max(current_price, base_price)
        except Exception as e:
            print("Price parsing error:", e)
            price = product_data.get("price", "")

        # Image processing
        image_string = product_data.get("product_images", "")
        images = [img.strip() for img in image_string.split(',') if img.strip()]
        
        in_watchlist = bool(fav_data and fav_data != "None")
    else:
        name, brand, description, price, db_product_id, images, in_watchlist = "", "", "", "", "", [], False

    return render_template(
        "product_details.html",
        name=name,
        brand=brand,
        description=description,
        price=price,
        images=images,
        product_id=str(db_product_id),
        in_watchlist=in_watchlist,
        fetch_bids=fetch_bids or [],
        competitors=competitors or []  # ✅ Add this line
    )


@app.route('/place_bid', methods=['POST'])
def place_bid():
    data = request.get_json()
    product_id = data.get('product_id')
    bid_amount = data.get('bid_amount')

    # Define the task inline
    def run_bid():
        place_bid_result = api.place_bid_price(product_id, bid_amount, user_id="999")
        print("place_bid:", place_bid_result)
        print(f"Received bid of ₹{bid_amount} for product {product_id}")

    # Start the thread
    threading.Thread(target=run_bid).start()

    return jsonify({"message": "Bid is being processed in the background."})


@app.route('/buynow', methods=['POST'])
def buynow():
    product_id = request.form.get('product_id')
    result = {}

    
    def process_product():
        raw_cart_products = api.buy_product(product_id)
        print("raw_cart_products", raw_cart_products)

        if not raw_cart_products or not isinstance(raw_cart_products, (list, tuple)):
            result["error"] = "Invalid product data"
            return

        try:
            name = raw_cart_products[0]
            brand = raw_cart_products[1]
            description = raw_cart_products[2]
            price = raw_cart_products[3]
            #qty = raw_cart_products[4]
            qty = 1
            current_price = raw_cart_products[12]
            images = raw_cart_products[5].split(",")
            image = images[0].strip()

            product = {
                "product_id": product_id,
                "name": name,
                "price": current_price,
                "image": image,
                "qty": qty
            }

            total_price = int(current_price) * int(qty)

            print("product ", product)
            print("total_price ", total_price)

            result["product"] = product
            result["total_price"] = total_price
        except Exception as e:
            result["error"] = str(e)

    thread = threading.Thread(target=process_product)
    thread.start()
    thread.join()  # Wait for the thread to complete before rendering

    return render_template("buynow.html", cart_products=[result["product"]], total_price=result["total_price"], product_id=product_id)


@app.route("/create_order", methods=["POST"])
def create_order():
    data = request.get_json()
    amount = int(float(data["price"]) * 100)  # Convert ₹ to paise

    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })
    return jsonify(order)

@app.route("/verify", methods=["POST"])
def verify():
    username = request.cookies.get('username')
    data = request.get_json()

    print("data ", data)

    try:
        params_dict = {
            'razorpay_order_id': data['order_id'],
            'razorpay_payment_id': data['payment_id'],
            'razorpay_signature': data['signature']
        }

        razorpay_client.utility.verify_payment_signature(params_dict)

        print("=== Payment Verified Successfully ===")
        print("Payment ID:", data['payment_id'])
        print("Order ID:", data['order_id'])
        print("Signature:", data['signature'])
        print("price:", str(data['user']['price']))
        print("product_id:", str(data['user']['product_id']))

        # Prepare payment details for insert_payment
        payment_details = {
            "cf_payment_id": data['payment_id'],
            "order_id": data['order_id'],
            "order_amount": str(int(data['user']['price']) / 100),  # Convert paise to INR
            "payment_currency": "INR",
            "payment_amount": str(int(data['user']['price']) / 100),
            "payment_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "payment_completion_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "payment_status": "SUCCESS",
            "payment_message": "Payment verified successfully",
            "bank_reference": data.get('bank_reference', ""),
            "payment_group": data.get('payment_method', "card"),  # Default to card if not provided
            "payment_method": data.get('payment_method', "card"),
            "uniqueid": str(data['user']['product_id']),
            "contact": data.get('user', {}).get('phone', "")
        }

        print("payment_details ", payment_details)

        # Call insert_payment
        if api.insert_payment(payment_details):
            print("Payment details saved to database.")
        else:
            print("Failed to save payment details to database.")


        if 'user' in data:
            print("=== User Details ===")
            print("Name:", data['user']['name'])
            print("Phone:", data['user']['phone'])
            print("Address:", data['user']['address'])
            print("Pincode:", data['user']['pincode'])
            print("City:", data['user']['city'])
            print("State:", data['user']['state'])
            print("Price:", data['user']['price'])


        api.insert_orders(str(data['user']['product_id']), username, str(data['user']['price']), str(data['order_id']))

        return jsonify({ "redirect_url": "/paymentsuccess" })

    except Exception as e:
        print("Payment verification failed:", e)
        return jsonify({ "redirect_url": "/paymentfailed" })


@app.route("/paymentsuccess")
def paymentsuccess():
    return render_template("paymentsuccess.html")


@app.route("/paymentfailed")
def paymentfailed():
    return render_template("paymentfailed.html")
    

@app.route("/checkout", methods=["POST"])
def checkout():
    name = request.form.get("name")
    phone = request.form.get("phone")
    address = request.form.get("address")
    pincode = request.form.get("pincode")
    city = request.form.get("city")
    state = request.form.get("state")
    price = request.form.get("price")
    product_id = request.form.get("product_id")
    #price = 1000

    print("name ", name)
    print("phone ", phone)
    print("address ", address)
    print("pincode ", pincode)
    print("city ", city)
    print("state ", state)
    print("price ", price)
    print("product_id ", product_id)

    # You can now process or store the above data
    return render_template("checkout.html", name=name, phone=phone, address=address,
                           pincode=pincode, city=city, state=state, price=price, product_id=product_id)


@app.route("/favourite")
def favourite():
    username = request.cookies.get('username')
    result = {"products": []}

    def fetch_and_process():
        fetch_fav_product = api.fetch_fav_product(user_id=username)
        print("fetch_fav_product", fetch_fav_product)

        products = []
        for item in fetch_fav_product:
            name = item[0]
            brand = item[1]
            product_id = item[4]
            price = item[3]
            image_string = item[5]

            all_image = image_string.split(',')
            print("all_image", all_image)

            products.append({
                "brand": brand,
                "name": name,
                "price": price,
                "image": all_image[0].strip(),  # Use first image
                "product_id": str(product_id)
            })

        result["products"] = products

    # Start the thread and wait for it to finish
    thread = threading.Thread(target=fetch_and_process)
    thread.start()
    thread.join()

    return render_template("favourite.html", products=result["products"])


@app.route('/addtofav/<int:product_id>')
def addtofav(product_id):
    def async_add_to_fav(pid):
        print("Added to favorite (async):", pid)
        result = api.add_to_favourite(pid, "999")
        print("API Result:", result)
    
    # Start a new thread
    threading.Thread(target=async_add_to_fav, args=(product_id,)).start()

    return '', 200


@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    product_id = request.form.get("product_id")
    
    print("Adding to cart:", product_id)

    def async_add_to_fav(pid):
        print("Added to cary (async):", pid)
        result = api.add_to_cart(pid, "999")
        print("API Result:", result)
    
    # Start a new thread
    threading.Thread(target=async_add_to_fav, args=(product_id,)).start()

    # Store product in cart here (e.g., insert into DB or session)

    return redirect(url_for("dashboard"))  # Redirect to dashboard


@app.route("/cart")
def cart():
    username = request.cookies.get('username')
    result = {"cart_products": [], "total_price": 0}

    def fetch_and_process_cart():
        raw_cart_products = api.fetch_cart_product(user_id=username)
        print("raw_cart_products", raw_cart_products)

        cart_products = []
        total_price = 0

        for item in raw_cart_products:
            product_id, name, price, qty = item
            price = int(price)
            total_price += price * qty

            cart_products.append({
                'id': product_id,
                'product_id': str(product_id),
                'name': name,
                'price': price,
                'qty': qty,
                'image': '1.webp'  # Placeholder
            })

        result["cart_products"] = cart_products
        result["total_price"] = total_price

    # Start and wait for thread to finish
    thread = threading.Thread(target=fetch_and_process_cart)
    thread.start()
    thread.join()

    return render_template("cart.html", cart_products=result["cart_products"], total_price=result["total_price"])


@app.route('/remove_from_cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    print("remove product_id", product_id)
    username = request.cookies.get('username')
    user_id = username
    result_holder = {}

    def remove_product():
        result = api.remove_product_from_cart(product_id, user_id)
        print("result", result)
        result_holder["result"] = result

    # Start thread and wait for it to complete
    thread = threading.Thread(target=remove_product)
    thread.start()
    thread.join()

    return redirect(url_for('cart'))


@app.route("/search_products")
def search_products():
    result = {"products": []}

    def fetch_and_process():
        fetch_product = api.fetch_all_products()
        print("fetch_product", fetch_product)

        products = []
        for item in fetch_product:
            name = item[0]
            brand = item[1]
            product_id = item[2]
            price = item[3]
            image_string = item[4]

            all_image = image_string.split(',')
            print("all_image", all_image)

            products.append({
                "brand": brand,
                "name": name,
                "price": price,
                "image": all_image[0].strip(),  # Use first image
                "product_id": str(product_id)
            })

        result["products"] = products

    # Start thread and wait for completion
    thread = threading.Thread(target=fetch_and_process)
    thread.start()
    thread.join()

    return render_template("search_products.html", products=result["products"])


@app.route("/chat")
def chat():
    return render_template("chat.html")


@app.route("/send_message", methods=["POST"])
def send_message():
    user_msg = request.json.get("message")
    print("user_msg: ", user_msg)

    result = {}

    def fetch_response():
        try:
            client = genai.Client(api_key="AIzaSyDDsRayQsXO8Qo6vpUC_lGu3rDUSeLPQfk")
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[user_msg],
                config=types.GenerateContentConfig(
                    max_output_tokens=500,
                    temperature=0.1
                )
            )
            result["reply"] = response.text

        except Exception as e:
            result["reply"] = f"Error: {str(e)}"

    # Run Gemini API call in a separate thread
    thread = threading.Thread(target=fetch_response)
    thread.start()
    thread.join()  # Wait for thread to finish before sending response

    print("AI Response: ", jsonify({"reply": result["reply"]}))

    return jsonify({"reply": result["reply"]})


@app.route('/api/search_suggestions')
def search_suggestions():
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify({'products': []})

    result = {"products": []}

    def fetch_suggestions():
        products = api.search_product_db(query)
        results = []
        for p in products:
            results.append({
                'product_id': p[0],
                'name': p[1],
                'brand': p[2],
                'price': p[3],
                'image': '1.webp'  # Replace with actual image if available
            })
        result["products"] = results

    thread = threading.Thread(target=fetch_suggestions)
    thread.start()
    thread.join()

    return jsonify({'products': result["products"]})


@app.route("/terms_conditions")
def terms_conditions():
    return render_template("terms_conditions.html")


@app.route("/refund_policy")
def refund_policy():
    return render_template("refund_policy.html")


@app.route("/privacy_policy")
def privacy_policy():
    return render_template("privacy_policy.html")


@app.route("/myorders")
def myorders():
    username = request.cookies.get('username')
    result = {"cart_products": [], "total_price": 0}

    def fetch_and_process_orders():
        raw_cart_products = api.fetch_orders_product(user_id=username)
        print("raw_cart_products", raw_cart_products)

        cart_products = []
        total_price = 0

        for item in raw_cart_products:
            product_id, user_id, price, order_id, datetime_value, product_name = item
            price = int(price)
            total_price += price

            cart_products.append({
                'id': order_id,
                'product_id': str(product_id),
                'name': product_name,
                'price': price,
                'qty': 1,  # Default quantity
                'datetime': str(datetime_value),
                'image': '1.webp'  # Placeholder image
            })

        result["cart_products"] = cart_products
        result["total_price"] = total_price

    # Start thread and wait for it to finish
    thread = threading.Thread(target=fetch_and_process_orders)
    thread.start()
    thread.join()

    return render_template("myorders.html", cart_products=result["cart_products"], total_price=result["total_price"])


@app.route("/register_token", methods=['GET', 'POST'])
def register_token():
    if request.method == "GET":
        token = request.args.get("token")
        public_ip = request.remote_addr
    else:
        data = request.json
        token = data.get("token")
        public_ip = data.get("public_ip")

    session['token'] = token
    session['public_ip'] = public_ip

    print("Stored Token in Session:", session.get("token"))
    print("Stored Public IP:", session.get("public_ip"))

    def update_token():
        result = api.updatetoken("None", token, public_ip)
        print("updatetoken:", result)

    thread = threading.Thread(target=update_token)
    thread.start()
    thread.join()

    return jsonify({
        "message": "Token stored successfully",
        "token": token,
        "public_ip": public_ip
    })


@app.route("/pinkvilla")
def pinkvilla():
    profile = {
        "name": "Pink Villla",
        "bio": "The ONLY place for premium adult board games and accessories!",
        "avatar": "https://i.pravatar.cc/150?img=3",
        "links": [
            {"title": "Adultopoly", "url": "https://meesho.com/adultopoly-board-game--the-ultimate-adult-party-experience/p/8w5ue0?_ms=1.2"},
            {"title": "Adultopoly Drunk", "url": "https://meesho.com/adultopoly-drunk/p/90mg52?_ms=1.2"},
        ]
    }
    return render_template("pinkvilla.html", profile=profile)


if __name__ == '__main__':
    # app.run(debug=True)
    # app = WsgiToAsgi(app)
    #app.run(port=8080, debug=True)
    socketio.run(app, debug=True, port=8080, allow_unsafe_werkzeug=True)
