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
from collections import Counter
import time

from threading import Thread
import queue
import firebase_admin
from firebase_admin import credentials

# Disable SSL warnings (for testing only, not recommended for production)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


from flask_socketio import SocketIO, emit

app = Flask(__name__, static_folder='static')
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


# Only initialize once
# cred = credentials.Certificate("serviceAccountKey.json")
# firebase_admin.initialize_app(cred)


@app.route("/")
def index():

    return render_template('index.html')


@app.route('/save_token', methods=['POST'])
def save_token():
    executor = ThreadPoolExecutor()

    username = request.cookies.get('username')
    data = request.get_json()
    token = data.get('token')
    public_ip = data.get('public_ip')

    print("username ", username)
    print("🔐 Received Firebase Token:", token)
    print("🌐 Public IP Address:", public_ip)

    session['fcm_token'] = token  # optional
    session['public_ip'] = public_ip

    executor.submit(api.insert_fmctoken, token, public_ip, username or "none")

    return jsonify({"status": "success"})


@app.route('/firebase-messaging-sw.js')
def sw():
    return app.send_static_file('firebase-messaging-sw.js')


@app.route("/main")
def main():
    username = request.cookies.get('username')

    if username:
        session['username'] = username
        return redirect(url_for('dashboard'))
        
    else:
        return render_template('main.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    username = request.cookies.get('username')

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
    # if 'username' not in session:
    #     return redirect(url_for('login'))

    # else:
        
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
    username = session.get('username')
    print("username ", username)

    if not username:
        #executor.submit(api.insert_log, "None", "profile", "none")
        return redirect(url_for('login'))

    else:
        def fetch_data(username):
            return api.fetch_profile(username)

        try:
            # Use ThreadPoolExecutor to get return value
            with ThreadPoolExecutor() as executor:
                future = executor.submit(fetch_data, username)
                profile_details = future.result()  # Wait for result

            return render_template("profile.html", name=profile_details[0], email=profile_details[2])

        except Exception as e:
            print(e)
            return redirect(url_for('login'))


@app.route("/seller_profile")
def seller_profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username')

    print("username ", username)

    def fetch_data(username):
        return api.fetch_seller_profile(username)

    # Use ThreadPoolExecutor to get return value
    with ThreadPoolExecutor() as executor:
        future = executor.submit(fetch_data, username)
        profile_details = future.result()  # Wait for result

    return render_template("seller_profile.html")


@app.route('/contactus', methods=['GET', 'POST'])
def contactus():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Get required data from request
        username = session.get('username')
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
    # if 'username' not in session:
    #     return redirect(url_for('login'))
    
    username = session.get('username')

    print("username", username)
    print("product_id", product_id)

    # Use thread pool to fetch product & bid data concurrently
    with ThreadPoolExecutor() as executor:
        futures = {
            'product': executor.submit(api.fetch_product_details, product_id, user_id=username),
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
        description = product_data.get("discription", "")
        db_product_id = product_data.get("product_id", "")
        min_qty = product_data.get("min_qty", "")
        
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

        print("in_watchlist ", fetch_product)

        print("description ", description)
    else:
        name, brand, description, price, db_product_id, images, in_watchlist = "", "", "", "", "", [], False

    return render_template(
        "product_details.html",
        name=name,
        brand=brand,
        description=description,
        price=price,
        min_qty=min_qty,
        images=images,
        product_id=str(db_product_id),
        in_watchlist=in_watchlist,
        fetch_bids=fetch_bids or [],
        competitors=competitors or [],  # ✅ Add this line
        username=username
    )


@app.route('/place_bid', methods=['POST'])
def place_bid():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    data = request.get_json()
    product_id = data.get('product_id')
    bid_amount = data.get('bid_amount')
    username = session.get('username')

    def run_bid():
        place_bid_result = api.place_bid_price(product_id, bid_amount, user_id=username)
        print("place_bid:", place_bid_result)
        print(f"Received bid of ₹{bid_amount} for product {product_id}")

        fetch_tokens = api.fetch_fmc_tokens(product_id)
        print("fetch_tokens", fetch_tokens)

        title = "New Bid Placed"
        body = f"New bid placed of ₹{bid_amount}. Check now!"
        
        for token_data in fetch_tokens:
            token = token_data.get("token")
            if token:
                if not api.send_fcm_notification(token, title, body):
                    print(f"Removing invalid token: {token}")
                    api.remove_fcm_token(token)  # Optional DB cleanup

    threading.Thread(target=run_bid).start()

    return jsonify({"message": "Bid is being processed and notifications are being sent."})


@app.route('/buynow', methods=['POST'])
def buynow():
    if 'username' not in session:
        return redirect(url_for('login'))
    
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
            qty = raw_cart_products[12]
            # qty = 1
            current_price = raw_cart_products[13]
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

    epoch_id = f"{int(time.time() * 1000)}{random.randint(100, 999)}"

    session["epoch"] = epoch_id

    print("Generated Epoch ID:", epoch_id)

    return render_template("buynow.html", cart_products=[result["product"]], total_price=result["total_price"], product_id=product_id, username=username, epoch_id=epoch_id)


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
    username = session.get('username')
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
            "username": str(data['user']['username']),
            "epoch_id": str(data['user']['epoch_id'])
        }

        print("payment_details ", payment_details)

        # # Call insert_payment
        # if api.insert_payment(payment_details):
        #     print("Payment details saved to database.")
        # else:
        #     print("Failed to save payment details to database.")


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
            print("epoch_id:", data['user']['epoch_id'])


        # insert_orders = api.insert_orders(
        #     str(data['user']['product_id']),
        #     str(data['user']['username']),
        #     str(data['user']['price']),
        #     "success",
        #     str(data['order_id']),
        #     str(data['user']['epoch_id'])
        # )
            
        # Step 3: Background function for DB inserts
        def background_db_tasks():
            print("🧵 Starting background DB insert thread...")
            if api.insert_payment(payment_details):
                print("✅ Payment inserted")
            else:
                print("❌ Payment insert failed")

            result = api.insert_orders(
                str(data['user']['product_id']),
                str(data['user']['username']),
                str(data['user']['price']),
                "success",
                str(data['order_id']),
                str(data['user']['epoch_id'])
            )
            print("✅ Order insert result:", result)

        # Step 4: Start thread
        thread = Thread(target=background_db_tasks)
        thread.start()

        # print("insert_orders ", insert_orders)

        return jsonify({ "redirect_url": "/paymentsuccess" })

    except Exception as e:
        # insert_orders = api.insert_orders(
        #     str(data['user']['product_id']),
        #     str(data['user']['username']),
        #     str(data['user']['price']),
        #     "failed",
        #     str(data['order_id']),
        #     str(data['user']['epoch_id'])
        # )

        # print("insert_orders ", insert_orders)

        # Thread for failed order insert
        def failed_order_insert():
            result = api.insert_orders(
                str(data['user']['product_id']),
                str(data['user']['username']),
                str(data['user']['price']),
                "failed",
                str(data['order_id']),
                str(data['user']['epoch_id'])
            )
            print("⚠️ Failed order insert:", result)

        Thread(target=failed_order_insert).start()

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
    # if 'username' not in session:
    #     return redirect(url_for('login'))
    
    name = request.args.get("name")
    phone = request.args.get("phone")
    address = request.args.get("address")
    pincode = request.args.get("pincode")
    city = request.args.get("city")
    state = request.args.get("state")
    price = request.args.get("price")
    product_id = request.args.get("product_id")
    username = request.args.get("username")
    epoch_id = request.args.get("epoch_id")

    print("name ", name)
    print("phone ", phone)
    print("address ", address)
    print("pincode ", pincode)
    print("city ", city)
    print("state ", state)
    print("price ", price)
    print("product_id ", product_id)
    print("username ", username)
    print("epoch_id ", epoch_id)

    return render_template("checkout.html", name=name, phone=phone, address=address,
                           pincode=pincode, city=city, state=state, price=price, product_id=product_id, username=username, epoch_id=epoch_id)


@app.route("/payment_verifier")
def payment_verifier():
    if 'username' not in session:
        return redirect(url_for('login'))

    epoch_id = request.args.get("epoch_id")
    print("Epoch ID in verifier:", epoch_id)

    return render_template("payment_verifier.html", epoch_id=epoch_id)


@app.route("/check_payment_status/<epoch_id>")
def check_payment_status(epoch_id):
    result_queue = queue.Queue()

    def check_status():
        try:
            status = api.payment_verifier(epoch_id)
            result_queue.put(status)
        except Exception as e:
            print("Error checking payment status:", e)
            result_queue.put(None)

    # Start thread
    thread = threading.Thread(target=check_status)
    thread.start()
    thread.join(timeout=5)  # max 5 seconds wait

    if not result_queue.empty():
        status = result_queue.get()
    else:
        status = None

    print("status ", status)
    return jsonify({"status": status})


@app.route("/favourite")
def favourite():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username')
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


@app.route("/bidproducts")
def bidproducts():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username')
    result = {"products": []}

    def fetch_and_process():
        bid_products = api.fetch_bid_product(user_id=username)
        print("fetch_bid_product", bid_products)

        products = []
        for item in bid_products:
            name = item[1]           # p.name
            product_id = item[0]     # p.product_id
            price = item[2]          # p.price
            max_price = item[4]      # b.max_price

            products.append({
                "name": name,
                "product_id": str(product_id),
                "price": price,
                "image": '1.jpg',  # TODO: fetch from DB if needed
                "max_price": str(max_price)
            })

        result["products"] = products

    thread = threading.Thread(target=fetch_and_process)
    thread.start()
    thread.join()

    return render_template("bidproducts.html", products=result["products"])


@app.route('/remove_from_fav', methods=['POST'])
def remove_from_fav():
    executor = ThreadPoolExecutor(max_workers=4)
    product_id = request.form.get('product_id')
    username = session.get('username')
    
    print("product_id ", product_id)
    print("username ", username)

    if username and product_id:
        executor.submit(api.remove_favorite, username, product_id)
        print(f"🧵 Removal task submitted for product {product_id}")
    
    return redirect(url_for('favourite'))  # Redirect back to fav page



@app.route('/addtofav/<int:product_id>')
def addtofav(product_id):
    username = session.get('username')

    def async_add_to_fav(pid):
        print("Added to favorite (async):", pid)
        result = api.add_to_favourite(pid, username)
        print("API Result:", result)
    
    # Start a new thread
    threading.Thread(target=async_add_to_fav, args=(product_id,)).start()

    return '', 200


@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    product_id = request.form.get("product_id")
    min_qty = request.form.get("min_qty")  # ✅ Capture min_qty from form
    
    print(f"Adding to cart: {product_id} | Min Qty: {min_qty}")
    username = session.get('username')

    def async_add_to_cart(pid, qty):
        print(f"Added to cart (async): {pid} | Qty: {qty}")
        result = api.add_to_cart(pid, username, qty)  # ✅ Pass qty to API
        print("API Result:", result)
    
    # Start a new thread
    threading.Thread(target=async_add_to_cart, args=(product_id, min_qty)).start()

    # Optionally store in DB/session here

    return redirect(url_for("dashboard"))



@app.route("/cart")
def cart():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    #username = session.get('username')
    username = session.get('username')

    print("username ", username)
    
    result = {"cart_products": [], "total_price": 0}

    def fetch_and_process_cart():
        raw_cart_products = api.fetch_cart_product(user_id=username)
        print("raw_cart_products", raw_cart_products)

        cart_products = []
        total_price = 0

        for item in raw_cart_products:
            product_id, name, price, qty = item
            price = int(price)
            total_price += price * int(qty)

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

    epoch_id = f"{int(time.time() * 1000)}{random.randint(100, 999)}"

    session["epoch"] = epoch_id

    print("Generated Epoch ID:", epoch_id)

    return render_template("cart.html", cart_products=result["cart_products"], total_price=result["total_price"], epoch_id=epoch_id, username=username)


@app.route('/remove_from_cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    print("remove product_id", product_id)
    username = session.get('username')
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
    # if 'username' not in session:
    #     return redirect(url_for('login'))
    
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
    if 'username' not in session:
        return redirect(url_for('login'))
    
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
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username')
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
    username = session.get('username')
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
        "name": "Bond & Beyond",
        "bio": "The ONLY place for premium adult board games and accessories!",
        "avatar": "https://i.pravatar.cc/150?img=3",
        "links": [
            {"title": "Adultopoly", "url": "https://meesho.com/adultopoly-board-game--the-ultimate-adult-party-experience/p/8w5ue0?_ms=1.2"},
            {"title": "Adultopoly Drunk", "url": "https://meesho.com/adultopoly-drunk/p/90mg52?_ms=1.2"},
            {"title": "Adultopoly Uno Card", "url": "https://meesho.com/18-uno-dare-adults-only-card-game-for-adult-game-night/p/92bm1q?_ms=1.2"},
            {"title": "Bond & Beyond Tower of Temptation", "url": "https://meesho.com/bond--beyond-tower-of-temptation-18/p/97tdkp?_ms=1.2"},
        ]
    }
    return render_template("pinkvilla.html", profile=profile)


@app.route("/seller_dashboard")
def seller_dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session.get('username')

    # Multi-threaded fetch
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(api.fetch_seller_dashboard, username, "approve")
        fetch_seller_dashboard = future.result()

    # Prepare orders and date counts
    orders = []
    date_list = []

    for product_id, price, dt, name in fetch_seller_dashboard:
        order_date = dt.strftime('%Y-%m-%d') if isinstance(dt, datetime.datetime) else str(dt).split(" ")[0]
        date_list.append(order_date)

        orders.append({
            'product_id': product_id,
            'name': name,
            'quantity': 1,
            'price': int(price),
            'date': order_date
        })

    # Count orders per date
    order_counts = Counter(date_list)

    # Use last 7 unique order dates
    unique_sorted_dates = sorted(set(date_list))[-7:]
    chart_data = [{'date': date, 'value': order_counts.get(date, 0)} for date in unique_sorted_dates]

    # Prepare chart labels and values
    dates = [d['date'] for d in chart_data]
    values = [d['value'] for d in chart_data]

    print("chart_data", chart_data)
    print("orders", orders)

    no_data = len(chart_data) == 0 and len(orders) == 0

    return render_template("seller_dashboard.html", dates=dates, values=values, orders=orders, no_data=no_data)



@app.route("/seller_pending_orders")
def seller_pending_orders():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username')
    
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
    if 'username' not in session:
        return redirect(url_for('login'))
    
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
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username')
    
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
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username')
    
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
    if 'username' not in session:
        return redirect(url_for('login'))
    
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
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username')
    
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
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username')

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
            "bidprice": bid_price if bid_price else "0",
            "product_id": product_id
        })

    return render_template("upload_products.html", orders=orders)


@app.route('/delete_product/<int:product_id>')
def delete_product(product_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    print("Delete product_id:", product_id)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(api.delete_product, product_id)
        delete_result = future.result()

    print("delete_product:", delete_result)
    return redirect(url_for('upload_products'))

    

@app.route("/upload_upload_page")
def upload_upload_page():
    return render_template("upload_upload_page.html")


@app.route('/seller_edit_product/<int:product_id>')
def seller_edit_product(product_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    print("edit product product_id:", product_id)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(api.fetch_seller_product_details, product_id)
        product_details = future.result()

    print("product_details:", product_details)

    # Map to dictionary
    product = {
        'name': product_details[0],
        'brand': product_details[1],
        'description': product_details[2],
        'price': product_details[3],
        'category': product_details[4],
        'brightness': product_details[5],
        'contrast_ratio': product_details[6],
        'hdr_hlg': product_details[7],
        'lamp_life_hrs_Normal_rco_mode': product_details[8],
        'type': product_details[9],
        'product_id': product_id

    }

    return render_template("seller_edit_product.html", product=product)


@app.route('/update_product_details', methods=['POST'])
def update_product_details():
    if 'username' not in session:
        return redirect(url_for('login'))

    # Retrieve data from form
    product_name = request.form.get('product_name')
    brand_name = request.form.get('brand_name')
    product_description = request.form.get('product_description')
    product_price = request.form.get('product_price')
    brand_category = request.form.get('brand_category')
    brand_brightness = request.form.get('brand_brightness')
    brand_contrast_ratio = request.form.get('brand_contrast_ratio')
    brand_hdr_hlg = request.form.get('brand_hdr_hlg')
    brand_lamp_life_hrs_Normal_rco_mode = request.form.get('brand_lamp_life_hrs_Normal_rco_mode')
    brand_type = request.form.get('brand_type')
    product_id = request.form.get('product_id')

    print("product_name:", product_name)
    print("brand_name:", brand_name)
    print("product_description:", product_description)
    print("product_price:", product_price)
    print("brand_category:", brand_category)
    print("brand_brightness:", brand_brightness)
    print("brand_contrast_ratio:", brand_contrast_ratio)
    print("brand_hdr_hlg:", brand_hdr_hlg)
    print("brand_lamp_life_hrs_Normal_rco_mode:", brand_lamp_life_hrs_Normal_rco_mode)
    print("brand_type:", brand_type)
    print("product_id:", product_id)

    # Use ThreadPoolExecutor to run update in a separate thread
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            api.update_product,
            product_name,
            brand_name,
            product_description,
            product_price,
            brand_category,
            brand_brightness,
            brand_contrast_ratio,
            brand_hdr_hlg,
            brand_lamp_life_hrs_Normal_rco_mode,
            brand_type,
            product_id
        )
        update_product = future.result()

    print("update_product ", update_product)
    
    return redirect(url_for('upload_products'))  # or some success page


@app.route('/submit_upload_button', methods=['POST'])
def submit_upload_button():
    executor = ThreadPoolExecutor(max_workers=4)

    username = session.get('username')

    category = request.form.get('category')
    product_name = request.form.get('product_name')
    brand_name = request.form.get('brand_name')
    product_price = request.form.get('product_price')
    start_bid_price = request.form.get('start_bid_price')
    min_qty = request.form.get('min_qty')
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
        start_bid_price,
        min_qty
    )

    print("args ", args)

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

    # 4️⃣ Find competitors in background
    executor.submit(api.find_compatitor, brand_name, product_name, category, product_id)

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
    # socketio.run(app, debug=True, host="0.0.0.0", port=8080, allow_unsafe_werkzeug=True)
    socketio.run(app, debug=True, port=5050, allow_unsafe_werkzeug=True)

