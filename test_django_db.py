import os
import django
from django.conf import settings

# First, let's see what settings Django loads
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'workbench.settings')

try:
    django.setup()
    print("✅ Django setup successful")
    
    # Now test the database connection
    from django.db import connection
    print("Testing database connection...")
    
    try:
        connection.ensure_connection()
        print("✅ Django database connection successful!")
    except Exception as e:
        print(f"❌ Django database connection failed: {e}")
        
except Exception as e:
    print(f"❌ Django setup failed: {e}")
