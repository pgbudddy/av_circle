import eventlet
eventlet.monkey_patch()


from flask import Flask, render_template, request, redirect, url_for, session, make_response, jsonify
from werkzeug.utils import secure_filename
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
import shutil


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
razorpay_client = razorpay.Client(auth=("rzp_live_KwWU7BnuboSLCV", "nXSeMZXRHJs0ZcAal1Aljmy5"))


# Upload folder configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# @app.route('/.well-known/assetlinks.json')
# def serve_assetlinks():
#     assetlinks = [{
#         "relation": ["delegate_permission/common.handle_all_urls"],
#         "target": {
#             "namespace": "android_app",
#             "package_name": "com.miniplex.miniplex",
#             "sha256_cert_fingerprints": ["A7:28:84:3D:60:E6:27:CC:61:94:14:4D:F0:EA:2A:4E:0D:82:7E:68:2E:10:83:60:CD:82:CA:2C:62:DD:C4:CD", "C8:36:0D:66:AA:6B:51:1A:A3:38:28:4A:18:DF:D0:41:54:0D:46:05:D7:27:95:EF:8F:E6:A7:24:3C:35:24:22"]
#         }
#     }]
#     response = make_response(jsonify(assetlinks))
#     response.headers['Content-Type'] = 'application/json'
#     return response


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


@app.route('/logout')
def logout():
    # Clear all session data
    session.clear()

    # Prepare response with redirection to login
    resp = make_response(redirect(url_for('login')))

    # Delete cookies by setting expiry to 0
    resp.set_cookie('username', '', expires=0)

    return resp


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

            session.clear()
            session['username'] = user_info.get("phone")  # or use email if preferred

            expire_date = datetime.datetime.now() + datetime.timedelta(days=30)
            resp = make_response(redirect(url_for('dashboard')))
            resp.set_cookie('username', user_info.get("phone"), expires=expire_date)

            return resp

            # return redirect(url_for('dashboard'))  # Update as needed

        else:
            return render_template("otp_verification.html", error="Enter valid OTP")
        
    else:
        # ✅ Return this for GET requests
        email = session.get('signup_info', {}).get('email', None)
        return render_template("otp_verification.html", email=email)


@app.route("/dashboard")
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
     
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


@app.route("/seller_profile")
def seller_profile():
    username = request.cookies.get('username')

    print("username ", username)

    def fetch_data(username):
        return api.fetch_seller_profile(username)

    # Use ThreadPoolExecutor to get return value
    with ThreadPoolExecutor() as executor:
        future = executor.submit(fetch_data, username)
        profile_details = future.result()  # Wait for result

    return render_template("seller_profile.html", name=profile_details[0], email=profile_details[2])


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
    username = request.cookies.get('username')

    print("username", username)
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
        competitors=competitors or [],  # ✅ Add this line
        username=username
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
    username = request.form.get('username')
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

    return render_template("buynow.html", cart_products=[result["product"]], total_price=result["total_price"], product_id=product_id, username=username)


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
        print("User ID:", data['order_id'])
        print("Signature:", data['signature'])
        print("price:", str(data['user']['price']))
        print("product_id:", str(data['user']['product_id']))
        print("username:", str(data['user']['username']))

        # Prepare payment details for insert_payment
        payment_details = {
            "cf_payment_id": data['payment_id'],
            "order_id": data['order_id'],
            "order_amount": str(int(data['user']['price'])),  # Convert paise to INR
            "payment_currency": "INR",
            "payment_amount": str(int(data['user']['price'])),
            "payment_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "payment_completion_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "payment_status": "SUCCESS",
            "payment_message": "Payment verified successfully",
            "bank_reference": data.get('bank_reference', ""),
            "payment_group": data.get('payment_method', "card"),  # Default to card if not provided
            "payment_method": data.get('payment_method', "card"),
            "uniqueid": str(data['user']['product_id']),
            "contact": data.get('user', {}).get('phone', ""),
            "username": str(data['user']['username'])
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
            print("username:", data['user']['username'])


        api.insert_orders(str(data['user']['product_id']), str(data['user']['username']), str(data['user']['price']), "pending", str(data['order_id']))

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
    

@app.route("/checkout", methods=["GET"])
def checkout():
    name = request.args.get("name")
    phone = request.args.get("phone")
    address = request.args.get("address")
    pincode = request.args.get("pincode")
    city = request.args.get("city")
    state = request.args.get("state")
    price = request.args.get("price")
    product_id = request.args.get("product_id")
    username = request.args.get("username")

    print("name ", name)
    print("phone ", phone)
    print("address ", address)
    print("pincode ", pincode)
    print("city ", city)
    print("state ", state)
    print("price ", price)
    print("product_id ", product_id)
    print("username ", username)

    return render_template("checkout.html", name=name, phone=phone, address=address,
                           pincode=pincode, city=city, state=state, price=price, product_id=product_id, username=username)


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
    username = request.cookies.get('username')
    if request.method == "GET":
        token = request.args.get("token")
        public_ip = request.remote_addr
    else:
        data = request.json
        token = data.get("token")
        public_ip = data.get("public_ip", request.remote_addr)

    # ✅ Store values in session (must be done in the main thread)
    session['token'] = token
    session['public_ip'] = public_ip

    print("Stored Token in Session:", token)
    print("Stored Public IP:", public_ip)

    # ✅ Capture values BEFORE threading (safe)
    def update_token_safe(tkn, ip):
        result = api.updatetoken("None", tkn, ip)
        print("updatetoken:", result)

    # ✅ Start thread (no .join(), let it run)
    threading.Thread(target=update_token_safe, args=(token, public_ip)).start()

    # result = api.updatetoken(username, token, public_ip)

    # print("updatetoken:", result)

    return jsonify({
        "message": "Token stored successfully",
        "token": token,
        "public_ip": public_ip
    })




@app.route("/forgetpassword", methods=["GET", "POST"])
def forgetpassword():
    if request.method == 'POST':
        details = request.form.get('details')

        print("Signup Creds ", details)

        checkuser = api.forgetpassword_checkuser(details)

        if checkuser[0] == True:
            otp = random.randint(1000, 9999)

            session['otp'] = str(otp)
            session['forgetpasswordemail'] = checkuser[1][1]  # ✅ Save email to session

            print("Otp ", otp)

            threading.Thread(target=api.send_mail, args=(checkuser[1][1], otp)).start()

            return redirect(url_for('forgetpassword_otp'))
        else:
            return render_template("forgetpassword.html", error="User does not exist!")
    else:
        return render_template("forgetpassword.html")


@app.route("/forgetpassword_otp", methods=["GET", "POST"])
def forgetpassword_otp():
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        stored_otp = str(session.get('otp'))

        if entered_otp == stored_otp:
            return redirect(url_for('change_password'))  # You can pass email if needed
        else:
            return render_template("otp_verification.html", error="Enter valid OTP")
    else:
        return render_template("otp_verification.html")


@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    forgetpasswordemail = session.get('forgetpasswordemail')  # ✅ Retrieve the email from session
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if str(password) == str(confirm_password):

            def threaded_send_otp(password, forgetpasswordemail):
                status = api.change_password(password, forgetpasswordemail)

            thread = threading.Thread(
                target=threaded_send_otp,
                args=(password, forgetpasswordemail)
            )
            thread.start()
        
            return redirect(url_for('login'))  # Update as needed
        else:
            return render_template("change_password.html", error="Password not mached")
        
    else:
        return render_template("change_password.html")


@app.route("/pinkvilla")
def pinkvilla():
    profile = {
        "name": "Pink Villla",
        "bio": "The ONLY place for premium adult board games and accessories!",
        "avatar": "https://i.pravatar.cc/150?img=3",
        "links": [
            {"title": "Adultopoly", "url": "https://meesho.com/adultopoly-board-game--the-ultimate-adult-party-experience/p/8w5ue0?_ms=1.2"},
            {"title": "Adultopoly Drunk", "url": "https://meesho.com/adultopoly-drunk/p/90mg52?_ms=1.2"},
            {"title": "Adultopoly Uno Card", "url": "https://meesho.com/18-uno-dare-adults-only-card-game-for-adult-game-night/p/92bm1q?_ms=1.2"},
        ]
    }
    return render_template("pinkvilla.html", profile=profile)


@app.route("/seller_dashboard")
def seller_dashboard():
    # Example chart data (past 7 days sales)
    chart_data = [
        {'date': (datetime.datetime.now() - datetime.timedelta(days=i)).strftime('%Y-%m-%d'), 'value': 100 + i * 10}
        for i in reversed(range(7))
    ]

    # Example orders
    orders = [
        {
            'product_id': 'P001',
            'name': 'Bluetooth Speaker',
            'quantity': 2,
            'price': 1499,
            'date': '2025-06-06 14:23'
        },
        {
            'product_id': 'P002',
            'name': 'LED Projector',
            'quantity': 1,
            'price': 4299,
            'date': '2025-06-07 10:15'
        },
        {
            'product_id': 'P002',
            'name': 'LED Projector',
            'quantity': 1,
            'price': 4299,
            'date': '2025-06-07 10:15'
        },
        {
            'product_id': 'P002',
            'name': 'LED Projector',
            'quantity': 1,
            'price': 4299,
            'date': '2025-06-07 10:15'
        },
        {
            'product_id': 'P002',
            'name': 'LED Projector',
            'quantity': 1,
            'price': 4299,
            'date': '2025-06-07 10:15'
        },
        {
            'product_id': 'P002',
            'name': 'LED Projector',
            'quantity': 1,
            'price': 4299,
            'date': '2025-06-07 10:15'
        },
        {
            'product_id': 'P002',
            'name': 'LED Projector',
            'quantity': 1,
            'price': 4299,
            'date': '2025-06-07 10:15'
        },
        {
            'product_id': 'P002',
            'name': 'LED Projector',
            'quantity': 1,
            'price': 4299,
            'date': '2025-06-07 10:15'
        },
        {
            'product_id': 'P002',
            'name': 'LED Projector',
            'quantity': 1,
            'price': 4299,
            'date': '2025-06-07 10:15'
        }
    ]

    # Extracting chart data into separate lists
    dates = [entry['date'] for entry in chart_data]
    values = [entry['value'] for entry in chart_data]


    return render_template("seller_dashboard.html", dates=dates, values=values, orders=orders)


@app.route("/seller_pending_orders")
def seller_pending_orders():
    username = request.cookies.get('username')
    
    raw_orders = api.fetch_seller_orders(username, 'pending')  # Must return 6 columns
    orders = []

    for order in raw_orders:
        price, dt, status, name, product_id, order_id = order  # Expect exactly 6

        formatted_date = datetime.datetime.strptime(
            str(dt), "%Y-%m-%d %H:%M:%S.%f"
        ).strftime("%d-%m-%Y")

        orders.append({
            "image": f"/static/images/product_images/{product_id}/1.webp",
            "name": name,
            "quantity": 1,
            "date": formatted_date,
            "price": int(price),
            "status": status,
            "product_id": product_id,
            "order_id": order_id
        })

    return render_template("seller_pending_orders.html", orders=orders)


@app.route('/update_order_status', methods=['POST'])
def update_order_status():
    data = request.get_json()
    order_id = data.get('order_id')
    product_id = data.get('product_id')
    user_id = data.get('user_id')
    status = data.get('status')

    print("data ", data)

    api.update_order_status(status, order_id)
    
    return jsonify({"message": "Order status updated successfully."})
    

@app.route("/seller_approved_orders")
def seller_approved_orders():
    username = request.cookies.get('username')
    
    raw_orders = api.fetch_seller_orders(username, 'approve')  # Must return 6 columns
    orders = []

    for order in raw_orders:
        price, dt, status, name, product_id, order_id = order  # Expect exactly 6

        formatted_date = datetime.datetime.strptime(
            str(dt), "%Y-%m-%d %H:%M:%S.%f"
        ).strftime("%d-%m-%Y")

        orders.append({
            "image": f"/static/images/product_images/{product_id}/1.webp",
            "name": name,
            "quantity": 1,
            "date": formatted_date,
            "price": int(price),
            "status": status,
            "product_id": product_id,
            "order_id": order_id
        })

    return render_template("seller_approved_orders.html", orders=orders)


@app.route("/seller_rejected_orders")
def seller_rejected_orders():
    username = request.cookies.get('username')
    
    raw_orders = api.fetch_seller_orders(username, 'reject')  # Must return 6 columns
    orders = []

    for order in raw_orders:
        price, dt, status, name, product_id, order_id = order  # Expect exactly 6

        formatted_date = datetime.datetime.strptime(
            str(dt), "%Y-%m-%d %H:%M:%S.%f"
        ).strftime("%d-%m-%Y")

        orders.append({
            "image": f"/static/images/product_images/{product_id}/1.webp",
            "name": name,
            "quantity": 1,
            "date": formatted_date,
            "price": int(price),
            "status": status,
            "product_id": product_id,
            "order_id": order_id
        })

    return render_template("seller_rejected_orders.html", orders=orders)


@app.route("/return_order")
def return_order():
    orders = [
        {
            "image": "/static/images/product_images/3/1.webp",
            "name": "Apple Watch Strap",
            "reason": "wrong product delivered",
            "date": "13-06-2025"
        },
        {
            "image": "/static/images/product_images/3/1.webp",
            "name": "Apple Watch Strap",
            "reason": "wrong product delivered",
            "date": "13-06-2025"
        },
        {
            "image": "/static/images/product_images/3/1.webp",
            "name": "Apple Watch Strap",
            "reason": "wrong product delivered",
            "date": "13-06-2025"
        },
        {
            "image": "/static/images/product_images/3/1.webp",
            "name": "Apple Watch Strap",
            "reason": "wrong product delivered",
            "date": "13-06-2025"
        },
        {
            "image": "/static/images/product_images/3/1.webp",
            "name": "Apple Watch Strap",
            "reason": "wrong product delivered",
            "date": "13-06-2025"
        },
        {
            "image": "/static/images/product_images/3/1.webp",
            "name": "Apple Watch Strap",
            "reason": "wrong product delivered",
            "date": "13-06-2025"
        },
        {
            "image": "/static/images/product_images/3/1.webp",
            "name": "Apple Watch Strap",
            "reason": "wrong product delivered",
            "date": "13-06-2025"
        },
    ]

    orders = []
    return render_template("return_order.html", orders=orders)


@app.route("/old_orders")
def old_orders():
    username = request.cookies.get('username')
    
    raw_orders = api.fetch_old_seller_orders(username)  # Must return 6 columns
    orders = []

    for order in raw_orders:
        price, dt, status, name, product_id, order_id = order  # Expect exactly 6

        formatted_date = datetime.datetime.strptime(
            str(dt), "%Y-%m-%d %H:%M:%S.%f"
        ).strftime("%d-%m-%Y")

        orders.append({
            "image": f"/static/images/product_images/{product_id}/1.webp",
            "name": name,
            "quantity": 1,
            "date": formatted_date,
            "price": int(price),
            "status": status,
            "product_id": product_id,
            "order_id": order_id
        })

    return render_template("old_orders.html", orders=orders)


@app.route("/upload_products")
def upload_products():
    username = request.cookies.get('username')

    results = api.fetch_upload_products(username)  # assuming your function returns the above list

    orders = []
    for name, price, product_id, bid_price in results:
        if not name or not price:
            continue  # skip empty records

        print("product_id ", product_id)

        orders.append({
            "image": f"/static/images/product_images/{product_id}/1.webp",
            "name": name,
            "date": datetime.datetime.now().strftime("%d-%m-%Y"),
            "price": price,
            "bidprice": bid_price if bid_price else "0"
        })

    return render_template("upload_products.html", orders=orders)


@app.route("/upload_upload_page")
def upload_upload_page():
    
    return render_template("upload_upload_page.html")


@app.route('/submit_upload_button', methods=['POST'])
def submit_upload_button():
    executor = ThreadPoolExecutor(max_workers=4)

    username = request.cookies.get('username')

    category = request.form.get('category')
    product_name = request.form.get('product_name')
    brand_name = request.form.get('brand_name')
    product_price = request.form.get('product_price')
    start_bid_price = request.form.get('start_bid_price')
    product_description = request.form.get('product_description')

    uploaded_files = request.files.getlist('product_images[]')
    image_names = []

    upload_folder = os.path.join('static', 'uploads')
    os.makedirs(upload_folder, exist_ok=True)

    count = 1
    for file in uploaded_files:
        if file and file.filename != '':
            if not file.filename.lower().endswith('.jpg'):
                print(f"Skipped non-JPG: {file.filename}")
                continue

            new_filename = f"{count}.jpg"
            save_path = os.path.join(upload_folder, new_filename)
            file.save(save_path)
            image_names.append(new_filename)
            count += 1

    image_string = ", ".join(image_names)

    args = (
        product_name,
        brand_name,
        product_description,
        product_price,
        image_string,
        category,
        "0", "0", "0", "0",
        category,
        username,
        start_bid_price
    )

    # Submit product insert task
    future_insert = executor.submit(api.insert_product, *args)

    # Wait for product_id to be returned
    product_id = future_insert.result()
    print("Returned product_id from thread:", product_id)

    # Create product image folder and move images
    product_image_folder = os.path.join('static', 'images', 'product_images', str(product_id))
    os.makedirs(product_image_folder, exist_ok=True)

    for img_name in image_names:
        src = os.path.join(upload_folder, img_name)
        dst = os.path.join(product_image_folder, img_name)
        shutil.move(src, dst)

    print("Images moved to:", product_image_folder)

    # Submit image_convertor to a separate thread (non-blocking)
    executor.submit(api.image_convertor, product_id)

    # Debug prints
    print("Category: ", category)
    print("Product Name: ", product_name)
    print("Product Brand Name: ", brand_name)
    print("Price: ", product_price)
    print("Start Bid Price: ", start_bid_price)
    print("Description: ", product_description)
    print("Images:", image_string)

    return redirect(url_for('upload_products'))



if __name__ == '__main__':
    # app.run(debug=True)
    # app = WsgiToAsgi(app)
    #app.run(port=8080, debug=True)
    socketio.run(app, debug=True, port=8080, allow_unsafe_werkzeug=True)
