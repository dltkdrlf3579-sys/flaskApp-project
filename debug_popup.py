import requests

# Start session and login
session = requests.Session()
login_url = 'http://127.0.0.1:5000/test-login-direct'
login_response = session.post(login_url, data={'login_id': 'dev_super'})
print(f"Login status: {login_response.status_code}")

# Test popup=true
response = session.get('http://127.0.0.1:5000/safe-workplace/SW2509190002?popup=true')
print(f"\nResponse status: {response.status_code}")

# Check for popup indicators
html = response.text

# Look for template extends
if '{% extends "popup-base.html" %}' in html:
    print("ERROR: Jinja2 template not being processed!")
elif 'class="popup-container"' in html:
    print("SUCCESS: Using popup template (found popup-container)")
elif 'window.close()' in html:
    print("SUCCESS: Using popup template (found window.close)")
elif '<body class="popup-body">' in html:
    print("SUCCESS: Using popup template (found popup-body)")
else:
    # Check for normal template indicators
    if 'class="sidebar"' in html:
        print("FAIL: Using normal template (found sidebar)")
    elif 'class="main-container"' in html:
        print("FAIL: Using normal template (found main-container)")
    else:
        print("UNKNOWN: Can't determine template type")

    # Show first part of response to debug
    print("\nFirst 1000 characters of response:")
    print(html[:1000])

    # Check if is_popup is in the response
    if 'is_popup' in html:
        print("\nFound 'is_popup' in response")

# Also test popup=1
print("\n" + "="*50)
print("Testing popup=1:")
response2 = session.get('http://127.0.0.1:5000/safe-workplace/SW2509190002?popup=1')
if 'class="popup-container"' in response2.text or 'window.close()' in response2.text:
    print("SUCCESS: popup=1 works")
else:
    print("FAIL: popup=1 doesn't work")