import math
import streamlit as st
import pandas as pd
import sqlite3
import os
import zipfile
from io import BytesIO
import time

# Function to initialize the database
def initialize_database():
    conn = sqlite3.connect('expenses.db')
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_type TEXT,
        category TEXT,
        project_number TEXT,
        type TEXT,
        quantity REAL,
        price_per_unit REAL,
        additional_cost REAL,
        product_name TEXT,
        vendor TEXT,
        description TEXT,
        price REAL,
        file_path TEXT,
        file_data BLOB
    )
    ''')
    conn.commit()
    return conn, c

# Function to save uploaded file with a specific name and return its path
def save_file(file_data, filename, folder='uploads'):
    if not os.path.exists(folder):
        os.makedirs(folder)
    file_path = os.path.join(folder, filename)
    it = 0
    while True:
        it += 1
        if os.path.isfile(file_path):
            file_path = os.path.join(folder, f"R_{it}.".join(filename.split('R.')))
        else:
            break
    with open(file_path, "wb") as f:
        f.write(file_data)
    return file_path

# Function to handle file upload
def handle_file_upload():
    uploaded_file = st.file_uploader("Upload a photo or PDF", type=["jpg", "jpeg", "png", "pdf"])
    if uploaded_file is not None:
        file_data = uploaded_file.getvalue()  # Get the file data as bytes
        file_extension = uploaded_file.name.split('.')[-1]  # Get the file extension
        return file_data, file_extension
    return None, None

# Function to display dynamic fields based on the expense category
def display_dynamic_fields(expense_category):
    fields = {}
    if expense_category == 'Fuel':
        fields['type'] = st.selectbox('Fuel Type', ['Petrol', 'Diesel', 'Electric'])
        fields['quantity'] = st.number_input('Fuel Quantity (liters or kWh)', min_value=0.0, value=0.0, format="%.3f", step=0.1)
        fields['price_per_unit'] = st.number_input('Price per Unit (OMR)', min_value=0.0, value=0.0, format="%.3f", step=0.1)
    elif expense_category == 'Customer Expense':
        fields['project_number'] = st.text_input('Project Number')
        fields['type'] = st.selectbox('Expense Type', ['Product Rent', 'Product Purchase', 'Service'])
        if fields['type'] in ['Product Rent', 'Product Purchase']:
            fields['product_name'] = st.text_input('Product Name')
            fields['quantity'] = st.number_input('Quantity', min_value=0.0, value=0.0, format="%.3f", step=1.0)
            fields['price_per_unit'] = st.number_input('Price per Unit (OMR)', min_value=0.0, value=0.0, format="%.3f", step=0.1)
    
    fields['vendor'] = st.text_input('Vendor Name')
    fields['description'] = st.text_area('Description')
    
    # Calculate total price automatically
    if expense_category == 'Fuel' or (expense_category == 'Customer Expense' and fields.get('type') in ['Product Rent', 'Product Purchase']):
        total_price = fields.get('quantity', 0) * fields.get('price_per_unit', 0) + fields.get('additional_cost', 0)
        st.number_input('Price', value=total_price, disabled=True, format="%.3f")
        fields['price'] = total_price  # Store total price in fields
    else:
        fields['price'] = st.number_input('Price (OMR)', min_value=0.0, format="%.3f", step=0.1)
    return fields

# Function to validate required fields
def validate_fields(vehicle_type, category, fields, file_data):
    required_fields = ['price']
    if category == 'Fuel':
        required_fields.extend(['type', 'quantity', 'price_per_unit'])
    elif category == 'Customer Expense':
        required_fields.extend(['project_number', 'type', 'quantity', 'price_per_unit'])
        if fields.get('type') in ['Product Rent', 'Product Purchase']:
            required_fields.append('product_name')
    required_fields.extend(['vendor', 'description'])

    missing_fields = [field for field in required_fields if not fields.get(field)]
    if not vehicle_type or not category or not file_data:
        return False, "Please complete all required fields including uploading a file."
    elif missing_fields:
        return False, f"Please complete all required fields: {', '.join(missing_fields)}."
    return True, ""

# Function to save data to the database
def save_to_database(c, data):
    c.execute('''
    INSERT INTO expenses (vehicle_type, category, project_number, vendor, type, quantity, price_per_unit, additional_cost, product_name, description, price, file_path, file_data)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', data)
    c.connection.commit()
    show_popup("Data saved successfully to the database!")

# Function to display success message as a popup in the center of the screen
def show_popup(message):
    if 'show_popup' not in st.session_state:
        st.session_state['show_popup'] = False

    if st.session_state['show_popup']:
        popup_html = f"""
        <div id="popup" style="position: fixed; 
                    top: 50%; left: 50%; 
                    transform: translate(-50%, -50%); 
                    background-color: #28a745; 
                    color: white; 
                    padding: 20px; 
                    border-radius: 5px; 
                    text-align: center; 
                    box-shadow: inset 0 0 10px 1px rgba(0,0,0,0.75); 
                    z-index: 9999;">
            {message}
        </div>
        <script>
        setTimeout(function() {{
            var popup = document.getElementById('popup');
            if (popup) {{
                popup.style.display = 'none';
            }}
        }}, 2000); // 2 seconds
        </script>
        """
        st.markdown(popup_html, unsafe_allow_html=True)
        st.session_state['show_popup'] = False
        time.sleep(2)
        st.rerun()

# Function to save data to a CSV file
def save_to_csv(df: pd.DataFrame):
    output = BytesIO()
    df[df.columns.to_list()[:-1]].to_csv(output, index=False)
    output.seek(0)
    return output

# Function to create a zip file containing the CSV and uploads folder
def create_zip_with_csv_and_uploads(csv_data, csv_filename='expenses.csv', uploads_folder='uploads'):
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Write the CSV file to the zip archive
        zipf.writestr(csv_filename, csv_data.getvalue())

        # Include all files in the uploads folder
        for foldername, subfolders, filenames in os.walk(uploads_folder):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                # Add files to the zip with relative paths including the uploads folder
                arcname = os.path.join('uploads', os.path.relpath(file_path, uploads_folder))
                zipf.write(file_path, arcname)

    zip_buffer.seek(0)
    return zip_buffer

# Function to view all database entries in a table format with file type and size
def view_all_entries(c):
    c.execute("SELECT * FROM expenses")
    records = c.fetchall()
    if records:
        columns = [desc[0] for desc in c.description]
        df = pd.DataFrame(records, columns=columns)
        
        # Create a new column 'File Info' with file name and size information
        df['File Name'] = df.apply(lambda row: get_file_info(row['file_path']), axis=1)
        
        # Drop file_path and file_data columns from the DataFrame for display
        df = df.drop(columns=['file_path', 'file_data'])
        
        st.dataframe(df)
    else:
        st.write("No records found in the database.")

# Helper function to get file information (name and size)
def get_file_info(file_path):
    if file_path and os.path.exists(file_path):
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        human_readable_size = convert_size(file_size)
        return f"{file_name} ({human_readable_size})"
    return "No File"

# Helper function to convert file size to a human-readable format
def convert_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

# Function to view a single database entry based on search ID
def view_single_entry(c, search_id):
    c.execute("SELECT * FROM expenses WHERE id = ?", (search_id,))
    record = c.fetchone()
    if record:
        columns = [desc[0] for desc in c.description]
        row = dict(zip(columns, record))
        
        st.subheader(f"Entry ID: {row['id']}")
        st.write(f"Vehicle Type: {row['vehicle_type']}")
        st.write(f"Category: {row['category']}")
        if row['project_number']:
            st.write(f"Project Number: {row['project_number']}")
        if row['type']:
            st.write(f"Type: {row['type']}")
        if row['product_name']:
            st.write(f"Product Name: {row['product_name']}")
        if row['quantity']:
            st.write(f"Quantity: {row['quantity']}")
        st.write(f"Price per Unit: {row['price_per_unit']:.3f} OMR")
        additionalCost = row['additional_cost'] if not str(row['additional_cost']) in ['None', 'nan'] else 0.0
        st.write(f"Additional Cost: {additionalCost:.3f} OMR")
        st.write(f"Total Price: {row['price']:.3f} OMR")
        st.write(f"Vendor Name: {row['vendor']}")
        st.write(f"Description: {row['description']}")
        
        if row['file_path']:
            file_type = row['file_path'].split('.')[-1].lower()
            if file_type in ['jpg', 'jpeg', 'png']:
                st.image(row['file_path'], width=200)
            elif file_type == 'pdf':
                with open(row['file_path'], "rb") as file:
                    st.download_button(
                        label="Download PDF",
                        data=file,
                        file_name=row['file_path'].split("/")[-1],
                        mime="application/pdf"
                    )
        st.write("---")
    else:
        st.write("No record found with this ID.")

# Function to download the SQLite database file
def download_db_file(db_path):
    with open(db_path, "rb") as f:
        db_data = f.read()
    return db_data

# Function to handle the main app logic
def main():
    global pageOption
    # Initialize database connection
    db_path = 'expenses.db'
    conn, c = initialize_database()
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    if st.sidebar.button("Add Expense"):
        st.session_state['Page'] = "Add"
    if st.sidebar.button("View Expenses"):
        st.session_state['Page'] = "View"

    # Determine page based on session state
    if 'Page' in st.session_state:
        pageOption = st.session_state['Page']
    else:
        pageOption = ""

    if pageOption == "Add":
        st.title('Add Vehicle Expense')

        # File upload handler
        file_data, file_extension = handle_file_upload()
        
        # Vehicle type selection
        vehicle_type = st.selectbox('Vehicle Type', ['Car', "Pickup", "Hi-ab", "Bus", 'Truck', 'Motorcycle', 'Other'])
        
        # Expense category selection
        expense_category = st.selectbox('Category of Expense', ['Fuel', 'Maintenance', 'Customer Expense', 'Other'])
        
        # Display dynamic fields based on category
        fields = display_dynamic_fields(expense_category)
        
        # Save the data to files and database
        if st.button('Save Data'):
            # Validate required fields
            is_valid, validation_message = validate_fields(vehicle_type, expense_category, fields, file_data)
            if is_valid:
                # Generate the filename for saving the uploaded file
                filename = f"{vehicle_type}_{expense_category}_{fields.get('type', 'NA')}_{fields.get('price', 0):.3f}_OMR.{file_extension}"
                # Save the file with the generated filename
                
                file_path = save_file(file_data, filename)

                # Prepare data for insertion
                data = (
                    vehicle_type,
                    expense_category,
                    fields.get('project_number'),
                    fields.get('vendor'),
                    fields.get('type'),
                    round(fields.get('quantity', 0.0), 3),
                    round(fields.get('price_per_unit', 0.0), 3),
                    round(fields.get('additional_cost', 0.0), 3),
                    fields.get('product_name'),
                    fields.get('description'),
                    round(fields.get('price', 0.0), 3),
                    file_path,
                    file_data
                )
                
                # Insert into database
                save_to_database(c, data)
                # Set the popup to be displayed
                st.session_state['show_popup'] = True
            else:
                st.warning(validation_message)
    
    elif pageOption == "View":
        st.title('View Vehicle Expenses')
        
        # Search by ID
        search_id = st.text_input("Search by ID (leave blank to view all)")
        if search_id:
            try:
                search_id = int(search_id)
            except ValueError:
                st.warning("Please enter a valid ID.")
                search_id = None
        
        # Display entries based on search ID or show all entries
        if search_id:
            view_single_entry(c, search_id)
        else:
            view_all_entries(c)
        
            # Download options
            c.execute("SELECT * FROM expenses")
            records = c.fetchall()
            if records:
                columns = [desc[0] for desc in c.description]
                df = pd.DataFrame(records, columns=columns)
                if st.button('Download'):
                    # Create CSV and then zip with uploads folder
                    csv_data = save_to_csv(df)
                    zip_data = create_zip_with_csv_and_uploads(csv_data)
                    st.download_button(
                        label="Download Excel/CSV with Files in ZIP",
                        data=zip_data,
                        file_name='expenses_with_uploads.zip',
                        mime='application/zip'
                    )
                    db_data = download_db_file(db_path)
                    st.download_button(
                        label="Download Database File",
                        data=db_data,
                        file_name=db_path,
                        mime="application/octet-stream"
                    )
    
    # Display the popup if needed
    show_popup("Data saved successfully to the database!")
    
    # Close database connection
    conn.close()

# Run the main function
if __name__ == '__main__':
    main()
