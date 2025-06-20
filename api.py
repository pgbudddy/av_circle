from conn import *
import datetime
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import os
from PIL import Image


def login(number, password):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        # Use BINARY to enforce case sensitivity for the password
        query = 'SELECT * FROM signup WHERE number=%s AND BINARY password=%s'
        mycursor.execute(query, (number, password))  # Use parameterized query to prevent SQL injection
        
        # Fetch the result
        myresult = mycursor.fetchone()

        # Check if the user exists
        if myresult is None:
            return False
        else:
            return True

    except Exception as e:
        print("Error:", e)  # Log the error for debugging
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)

    
def fetch_userid(number):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        query = 'SELECT * FROM signup where number="'+str(number)+'"'
        mycursor.execute(query)
        myresult = mycursor.fetchone()
        
        if myresult == None:  
            return False
        else:
            return myresult[0], myresult[1], myresult[6]

    except:
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def get_recent_messages():
    try:
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=7)
        mydb = get_db_connection()
        mycursor = mydb.cursor(buffered=True)
        mycursor.execute("SELECT username, message, timestamp FROM messages WHERE timestamp >= %s ORDER BY timestamp ASC", (cutoff_date,))
        myresult = mycursor.fetchall()

        if myresult == None:
            return False
        else:
            return myresult
    
    except:
        return False
    
    finally:
        close_connection(mydb, mycursor)


def contactus(userid, name, number, message):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        date = datetime.datetime.now()
        trade = "INSERT INTO contactus (userid, name, number, message, datetime) VALUES (%s, %s, %s, %s, %s)"
        mycursor.execute(trade, (userid, name, number, message, date))
        mydb.commit()
        
        # Check if insertion was successful
        if mycursor.rowcount > 0:
            print("Data inserted successfully.")
            return True
        else:
            print("Data insertion failed.")
            return False
        
    except Exception as e:
        print(e)
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def insert_payment(payment):
    print("payment ", payment)
    mydb = None
    mycursor = None
    try:
        mydb = get_db_connection()
        mycursor = mydb.cursor(buffered=True)

        # Access attributes using dot notation
        cf_payment_id = payment["cf_payment_id"]
        order_id = payment["order_id"]
        order_amount = payment["order_amount"]
        payment_currency = payment["payment_currency"]
        payment_amount = payment["payment_amount"]
        payment_time = payment["payment_time"]
        payment_completion_time = payment["payment_completion_time"]
        payment_status = payment["payment_status"]
        payment_message = payment["payment_message"]
        bank_reference = payment["bank_reference"]
        payment_group = payment["payment_group"]
        payment_method = payment["payment_method"]  # Assuming this is already a string or valid data
        uniqueid = payment["uniqueid"]  # Use getattr to avoid AttributeError if email is missing
        contact = payment["contact"] 

        date = datetime.datetime.now()

        # Prepare the INSERT query
        trade = """
            INSERT INTO payments (
                cf_payment_id, order_id, order_amount, payment_currency, payment_amount, 
                payment_time, payment_completion_time, payment_status, payment_message, 
                bank_reference, payment_group, payment_method, uniqueid, contact, datetime
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        # Execute the query
        mycursor.execute(trade, (
            str(cf_payment_id), str(order_id), str(order_amount), str(payment_currency), str(payment_amount), 
            str(payment_time), str(payment_completion_time), str(payment_status), str(payment_message), 
            str(bank_reference), str(payment_group), str(payment_method), str(uniqueid), str(contact), str(date)
        ))

        mydb.commit()

        if mycursor.rowcount > 0:
            print("Data inserted successfully.")
            return True
        else:
            print("Data insertion failed.")
            return False

    except Exception as e:
        print("Error:", e)
        return False

    finally:
        if mycursor:
            mycursor.close()
        if mydb:
            mydb.close()


def insert_orders(product_id, user_id, price, order_id):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        date = datetime.datetime.now()
        trade = "INSERT INTO orders (product_id, user_id, price, order_id, staus, datetime) VALUES (%s, %s, %s, %s, %s, %s)"
        mycursor.execute(trade, (product_id, user_id, price, order_id, date))
        mydb.commit()
        
        # Check if insertion was successful
        if mycursor.rowcount > 0:
            print("Data inserted successfully.")
            return True
        else:
            print("Data insertion failed.")
            return False
        
    except Exception as e:
        print(e)
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def signup(name, email, number, password, public_ip):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        date = datetime.datetime.now()
        # public_ip = get_public_ip()

        trade = "INSERT INTO signup (name, number, email_id, password, user_id, public_ip, datetime) values ('"+str(name)+"', '"+str(number)+"', '"+str(email)+"', '"+str(password)+"', '0', '"+str(public_ip)+"', '"+str(date)+"')"
        mycursor.execute(trade)
        mydb.commit()
        
        # Check if insertion was successful
        if mycursor.rowcount > 0:
            print("Data inserted successfully.")
            return True
        else:
            print("Data insertion failed.")
            return False
        
    except:
        return False
    
    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def change_password(number, password):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        print(number)
        trade = "update signup set password = '"+str(password)+"' where number = '"+str(number)+"'"
        mycursor.execute(trade)
        mydb.commit()
        
        # Check if insertion was successful
        if mycursor.rowcount > 0:
            print("Data inserted successfully.")
            return True
        else:
            print("Data insertion failed.")
            return False
        
    except:
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def send_mail(receiver_email, otp):
    # Sender's Gmail credentials
    sender_email = "carrykar108@gmail.com"
    sender_password = os.getenv("GMAIL_APP_PASSWORD", "typz bgyg bcgs jxfs")  # Use env var for security
    sender_alias = "noreply@avcircles.com"  # Custom domain email

    # Email subject
    subject = "Welcome to AV Circle"

    # HTML content with absolute URLs
    html_body = """
    <html>
        <head>
            <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
            <style>
                body {
                    font-family: 'Poppins', sans-serif; 
                    color: #333; 
                    background-color: #f4f4f4; 
                    padding: 20px;
                    display: flex;
                    justify-content: center;
                    align-items: flex-start;
                    height: 100vh;
                    margin: 0;
                }
                .mainbox {
                    border: 1px solid lightgrey;
                    border-radius: 10px;
                    padding: 50px 50px;
                    width: 40%;
                }
                h1 {
                    font-family: 'Poppins', sans-serif;
                    color: #0747A9;
                    font-style: normal;
                    font-size: 25px;
                }
                p {
                    font-family: 'Poppins', sans-serif;
                    font-size: 16px;
                    font-style: normal;
                    color: black;
                }
                .button {
                    background-color: #0747A9;
                    color: white;
                    padding: 10px 20px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    border-radius: 5px;
                    font-style: normal;
                    text-decoration: none;
                }
                .line {
                    border-top: 1px solid lightgrey;
                }
            </style>
        </head>
        <body>
            <div class="mainbox">
                <img src="{{ url_for('static', filename='images/play_store_logo.png') }}"style="width: 50px;" alt="Logo">
                <p>Hello User,</p>
                <p>Welcome to AV Circle! Your verification code is:</p>
                <h1>""" + str(otp) + """</h1>
                <br>
                <div class="line"></div>
                <img src="{{ url_for('static', filename='images/play_store_logo.png') }}" style="margin-top: 30px; width: 30px;" alt="Logo">
                <p style="font-size: 13px;">Regards,<br>AV Circle Team</p>
            </div>
        </body>
    </html>
    """

    # Setup the MIME
    message = MIMEMultipart()
    message["From"] = f"AV Circle <{sender_alias}>"  # Format with display name
    message["To"] = receiver_email
    message["Subject"] = subject

    # Attach HTML body
    message.attach(MIMEText(html_body, "html"))

    # Gmail SMTP server configuration
    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    try:
        # Database connection (assuming get_db_connection is defined)
        mydb = get_db_connection()
        mycursor = mydb.cursor(buffered=True)

        # Connect to Gmail's SMTP server
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Secure the connection
        server.login(sender_email, sender_password)  # Login with Gmail credentials

        # Send email with sender_email as envelope sender
        server.sendmail(sender_email, receiver_email, message.as_string())
        print(f"Email sent successfully from {sender_alias}!")
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False

    finally:
        close_connection(mydb, mycursor)  # Ensure DB connection is closed


def checkuser(email, number):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        query = 'SELECT * FROM signup where email_id="'+str(email)+'" OR number="'+str(number)+'" '
        mycursor.execute(query)
        myresult = mycursor.fetchone()
        print("myresult ", myresult)
        
        if myresult == None:  
            return False
        else:
            return True

    except:
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def forgetpassword_checkuser(details):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        query = 'SELECT number, email_id FROM signup where email_id="'+str(details)+'" OR number="'+str(details)+'" '
        mycursor.execute(query)
        myresult = mycursor.fetchone()
        print("myresult ", myresult)
        
        if myresult == None:  
            return False, 0
        else:
            return True, myresult

    except:
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)

    
def change_password(password, email_id):
    print(password, email_id)
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        trade = "UPDATE signup SET password='"+str(password)+"' WHERE email_id='"+str(email_id)+"'"
        mycursor.execute(trade)
        mydb.commit()
        
        return True
    
    except:
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def fetch_products():
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        query = 'SELECT name, brand, product_id, price, product_images FROM products LIMIT 20'
        mycursor.execute(query)
        myresult = mycursor.fetchall()

        print("myresult ", myresult)

        return myresult
        
    except:
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def fetch_all_products():
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        query = 'SELECT name, brand, product_id, price, product_images FROM products'
        mycursor.execute(query)
        myresult = mycursor.fetchall()

        print("myresult ", myresult)

        return myresult
        
    except:
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def fetch_profile(uniqueid):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        query = 'SELECT * FROM signup where number="'+str(uniqueid)+'"'
        mycursor.execute(query)
        myresult = mycursor.fetchone()

        # print(myresult)
        
        if myresult == None:  
            return False
        else:
            return myresult

    except:
        return False
    
    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)
        

def buy_product(product_id):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        query = 'SELECT p.*, COALESCE(MAX(b.price), p.price) AS current_price FROM products p LEFT JOIN bids b ON p.product_id = b.product_id WHERE p.product_id = %s GROUP BY p.product_id'
        mycursor.execute(query, (product_id,))
        product_result = mycursor.fetchone()
        return product_result
        
    except:
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def fetch_product_details(product_id, user_id):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()
        mycursor = mydb.cursor(dictionary=True, buffered=True)

        # Query to fetch product with max bid or default price
        query = 'SELECT p.product_id, p.name, p.discription, p.price, COALESCE(MAX(b.price), p.price) AS current_price, p.product_images FROM products p LEFT JOIN bids b ON p.product_id = b.product_id WHERE p.product_id = %s GROUP BY p.product_id, p.name, p.discription, p.price, p.product_images'
        mycursor.execute(query, (product_id,))
        product_result = mycursor.fetchone()

        print("product_result ", product_result)

        # Check if product is in user's favourites
        fav_query = 'SELECT * FROM favourite WHERE product_id = %s AND user_id = %s'
        mycursor.execute(fav_query, (product_id, user_id))
        fav_result = mycursor.fetchone()

        print("fav", fav_result)

        if fav_result:
            return product_result, fav_result
        else:
            return product_result, "None"

    except Exception as e:
        print("Error:", str(e))
        return False

    finally:
        close_connection(mydb, mycursor)


def place_bid_price(product_id, bid_amount, user_id):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        date = datetime.datetime.now()
        # public_ip = get_public_ip()

        trade = "INSERT INTO bids (user_id, price, product_id, datetime) values ('"+str(user_id)+"', '"+str(bid_amount)+"', '"+str(product_id)+"', '"+str(date)+"')"
        mycursor.execute(trade)
        mydb.commit()
        
        # Check if insertion was successful
        if mycursor.rowcount > 0:
            print("Data inserted successfully.")
            return True
        else:
            print("Data insertion failed.")
            return False
        
    except:
        return False
    
    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def fetch_bids_details(product_id):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Use dictionary cursor for better readability
        mycursor = mydb.cursor(dictionary=True, buffered=True)

        # Updated query with JOIN
        query = 'SELECT b.*, s.name FROM bids b JOIN signup s ON b.user_id = s.user_id WHERE b.product_id = %s'
        mycursor.execute(query, (product_id,))
        myresult = mycursor.fetchall()

        return myresult

    except Exception as e:
        print("Error:", str(e))
        return False

    finally:
        close_connection(mydb, mycursor)


def fetch_competitors(product_id):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Use dictionary cursor for better readability
        mycursor = mydb.cursor(dictionary=True, buffered=True)

        # Updated query with JOIN
        query = 'SELECT * FROM competitors WHERE product_id = %s'
        mycursor.execute(query, (product_id,))
        myresult = mycursor.fetchone()

        return myresult

    except Exception as e:
        print("Error:", str(e))
        return False

    finally:
        close_connection(mydb, mycursor)


def fetch_fav_product(user_id):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)

        query = 'SELECT p.* FROM products p JOIN favourite f ON p.product_id = f.product_id WHERE f.user_id = '+str(user_id)
        mycursor.execute(query)
        myresult = mycursor.fetchall()

        return myresult
        
    except:
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def add_to_favourite(product_id, user_id):
    print("save_message")
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        date = datetime.datetime.now()
        print(product_id, user_id, date)
        trade = "INSERT INTO favourite (product_id, user_id, datetime) VALUES (%s, %s, %s)"
        mycursor.execute(trade, (product_id, user_id, date))
        mydb.commit()
        
        # Check if insertion was successful
        if mycursor.rowcount > 0:
            print("Data inserted successfully.")
            return True
        else:
            print("Data insertion failed.")
            return False
        
    except Exception as e:
        print(e)
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def fetch_cart_product(user_id):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)

        query = '''
            SELECT 
                p.product_id,
                p.name,
                COALESCE(MAX(b.price), p.price) AS current_price,
                c.qty
            FROM 
                products p
            JOIN 
                cart c ON p.product_id = c.product_id
            LEFT JOIN 
                bids b ON p.product_id = b.product_id
            WHERE 
                c.user_id = %s
            GROUP BY 
                p.product_id, p.name, p.price, c.qty
        '''
        mycursor.execute(query, (user_id,))
        myresult = mycursor.fetchall()

        return myresult
        
    except:
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def fetch_orders_product(user_id):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)

        query = '''
        SELECT 
            o.product_id,
            o.user_id,
            o.price,
            o.order_id,
            o.datetime,
            p.name
        FROM 
            orders o
        JOIN 
            products p ON o.product_id = p.product_id
        WHERE 
            o.user_id = %s;
        '''
        mycursor.execute(query, (user_id,))
        myresult = mycursor.fetchall()

        return myresult

    except Exception as e:
        print("Error:", e)
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def fetch_seller_orders(user_id, status):
    try:
        mydb = get_db_connection()
        mycursor = mydb.cursor(buffered=True)

        query = '''
        SELECT o.price, o.datetime, o.status, p.name, p.product_id, o.order_id
        FROM orders o
        JOIN products p ON o.product_id = p.product_id
        WHERE o.user_id = %s AND o.status = %s;
        '''
        mycursor.execute(query, (user_id, status,))
        myresult = mycursor.fetchall()

        return myresult

    except Exception as e:
        print("Error:", e)
        return False

    finally:
        close_connection(mydb, mycursor)


def update_order_status(status, order_id):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        trade = "update orders set status = '"+str(status)+"' where order_id = '"+str(order_id)+"'"
        mycursor.execute(trade)
        mydb.commit()
        
        # Check if insertion was successful
        if mycursor.rowcount > 0:
            print("Data inserted successfully.")
            return True
        else:
            print("Data insertion failed.")
            return False
        
    except:
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def fetch_old_seller_orders(user_id):
    try:
        mydb = get_db_connection()
        mycursor = mydb.cursor(buffered=True)

        query = '''
        SELECT o.price, o.datetime, o.status, p.name, p.product_id, o.order_id
        FROM orders o
        JOIN products p ON o.product_id = p.product_id
        WHERE o.user_id = %s AND o.status = 'approve';
        '''
        mycursor.execute(query, (user_id,))
        myresult = mycursor.fetchall()

        return myresult

    except Exception as e:
        print("Error:", e)
        return False

    finally:
        close_connection(mydb, mycursor)


def remove_product_from_cart(product_id, user_id):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)

        # Use %s placeholders for MySQL
        mycursor.execute("DELETE FROM cart WHERE product_id = %s AND user_id = %s", (product_id, user_id))
        mydb.commit()

        if mycursor.rowcount > 0:
            print("Data removed successfully.")
            return True
        else:
            print("Data removal failed.")
            return False
        
    except Exception as e:
        print("Error:", e)
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def search_product_db(query):
    mydb = get_db_connection()

        # Create a cursor from the connection
    mycursor = mydb.cursor(buffered=True)
    
    mycursor.execute("""
        SELECT product_id, name, brand, price, product_images
        FROM products 
        WHERE LOWER(name) LIKE %s OR LOWER(brand) LIKE %s
    """, ('%' + query + '%', '%' + query + '%'))
    results = mycursor.fetchall()
    close_connection(mydb, mycursor)

    return results


def add_to_cart(product_id, user_id):
    print("save_message")
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        date = datetime.datetime.now()
        print(product_id, user_id, date)
        trade = "INSERT INTO cart (product_id, user_id, qty, datetime) VALUES (%s, %s, '1', %s)"
        mycursor.execute(trade, (product_id, user_id, date))
        mydb.commit()
        
        # Check if insertion was successful
        if mycursor.rowcount > 0:
            print("Data inserted successfully.")
            return True
        else:
            print("Data insertion failed.")
            return False
        
    except Exception as e:
        print(e)
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def insert_product(name, brand, discription, price, product_images, category, brightness, contrast_ratio, HDR_HLG, lamp_life_hrs_Normal_rco_mode, type, user_id, bid_price):
    print("save_message")
    try:
        # Get a connection from the pool
        mydb = get_db_connection()
        mycursor = mydb.cursor(buffered=True)

        date = datetime.datetime.now()

        # Insert into products table (product_id is AUTO_INCREMENT)
        insert_product = """
            INSERT INTO products(
                name, brand, discription, price, product_images, category,
                brightness, contrast_ratio, HDR_HLG,
                lamp_life_hrs_Normal_rco_mode, type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        mycursor.execute(insert_product, (
            name, brand, discription, price, product_images, category,
            brightness, contrast_ratio, HDR_HLG,
            lamp_life_hrs_Normal_rco_mode, type
        ))
        mydb.commit()

        # Get the auto-incremented product_id
        product_id = mycursor.lastrowid
        print("Inserted product_id:", product_id)

        # Insert into uploaded_products table (or orders, depending on your table name)
        insert_product_profile = """
            INSERT INTO uploaded_products(product_id, user_id, datetime)
            VALUES (%s, %s, %s)
        """
        mycursor.execute(insert_product_profile, (product_id, user_id, date))
        mydb.commit()

        print("Inserted uploaded_products")

        # Insert into bids table (or orders, depending on your table name)
        insert_bids = """
            INSERT INTO bids(user_id, price, product_id, datetime)
            VALUES (%s, %s, %s, %s)
        """
        mycursor.execute(insert_bids, (user_id, bid_price, product_id, date))
        mydb.commit()

        print("Inserted bids")

        if mycursor.rowcount > 0:
            print("All data inserted successfully.")
            return product_id
        else:
            print("All data insertion failed.")
            return False

    except Exception as e:
        print("Error:", e)
        return False

    finally:
        close_connection(mydb, mycursor)


def image_convertor(product_id):
    try:
        print(f"[image_convertor] Running for product_id: {product_id}")
        source_dir = f'static/images/product_images/{product_id}/'
        print(f"[image_convertor] Looking inside: {source_dir}")
        
        for filename in os.listdir(source_dir):
            if filename.lower().endswith((".jpeg", ".jpg",  ".png")):
                img = Image.open(os.path.join(source_dir, filename))
                webp_name = os.path.splitext(filename)[0] + '.webp'
                img.save(os.path.join(source_dir, webp_name), 'webp', quality=10)
                print(f"[image_convertor] Converted: {filename} -> {webp_name}")

        return True
    
    except Exception as e:
        print("Error in image_convertor:", e)
        return False
   


def fetch_upload_products(user_id):
    try:
        mydb = get_db_connection()

            # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        mydb = get_db_connection()
        mycursor = mydb.cursor(buffered=True)
        query = """
        SELECT 
            p.name,
            p.price AS original_price,
            p.product_id,
            COALESCE(MAX(b.price), 0) AS highest_bid_price
        FROM 
            products p
        LEFT JOIN 
            bids b ON p.product_id = b.product_id
        WHERE 
            p.product_id IN (
                SELECT product_id 
                FROM uploaded_products 
                WHERE user_id = %s
            )
        GROUP BY 
            p.product_id, p.name, p.price;
        """

        mycursor.execute(query, (user_id,))
        results = mycursor.fetchall()

        print("results ", results)

        return results
    
    except requests.RequestException as e:
        print(f"Error fetching IP address: {e}")
        return None
    
    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def get_public_ip():
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)
        
        response = requests.get("https://api.ipify.org?format=json")
        response.raise_for_status()
        ip_address = response.json()["ip"]
        return ip_address
    
    except requests.RequestException as e:
        print(f"Error fetching IP address: {e}")
        return None
    
    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)


def updatetoken(user_id, token, public_ip):
    try:
        # Get a connection from the pool
        mydb = get_db_connection()

        # Create a cursor from the connection
        mycursor = mydb.cursor(buffered=True)

        date = datetime.datetime.now()
        
        query = 'SELECT * FROM fcm_token where public_ip="'+str(public_ip)+'"'
        mycursor.execute(query)
        myresult = mycursor.fetchone()
        print("myresult: ", myresult)
        
        if myresult == None:  
            trade = "INSERT INTO fcm_token (user_id, token, public_ip, datetime) values ('"+str(user_id)+"', '"+str(token)+"', '"+str(public_ip)+"', '"+str(date)+"')"
            mycursor.execute(trade)
            mydb.commit()
            return "Token Inserted"
        
        else:
            trade = "UPDATE fcm_token SET user_id='"+str(user_id)+"', token='"+str(token)+"' WHERE public_ip='"+str(public_ip)+"'"
            mycursor.execute(trade)
            mydb.commit()
            return "Token Updated"

    except requests.RequestException as e:
        print("Error: ", e)
        return False

    finally:
        # Ensure that the cursor and connection are closed
        close_connection(mydb, mycursor)